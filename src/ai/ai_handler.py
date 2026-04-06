import os
import shutil
import subprocess
import time
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ..utils.logger import log


COMMON_WINDOWS_PATHS = [
    Path.home()
    / "Documents"
    / "LM Studio"
    / "resources"
    / "app"
    / ".webpack"
    / "lms.exe",
    Path.home() / "Documents" / "LM Studio" / "resources" / "app" / ".webpack",
    Path(os.environ.get("LOCALAPPDATA", "C:/Users/AppData/Local")) / "LM Studio",
    Path.home() / "Documents" / "LM Studio",
    Path("C:/Program Files/LM Studio"),
    Path("C:/Program Files (x86)/LM Studio"),
    Path.home() / "AppData" / "Local" / "LM Studio",
    Path.home() / "AppData" / "Local" / "Programs" / "LM Studio",
    Path.home() / "AppData" / "Roaming" / "LM Studio",
    Path(os.environ.get("ProgramData", "C:/ProgramData")) / "LM Studio",
    Path("D:/LM Studio"),
    Path.home() / "LM Studio",
]

COMMON_MAC_PATHS = [
    Path.home() / "Applications" / "LM Studio.app",
    Path("/Applications/LM Studio.app"),
]

COMMON_LINUX_PATHS = [
    Path.home() / ".local" / "bin" / "lmstudio",
    Path("/usr/local/bin/lmstudio"),
    Path("/usr/bin/lmstudio"),
]


@dataclass
class LMStudioStatus:
    available: bool
    server_running: bool
    model_loaded: bool
    correct_model: bool
    message: str


class LMStudioManager:
    def __init__(
        self,
        endpoint: str = "http://127.0.0.1:1234/v1",
        model_name: str = "openai/gpt-oss-20b",
        startup_timeout: int = 30,
    ):
        self.endpoint = endpoint
        self.model_name = model_name
        self.startup_timeout = startup_timeout
        self.lmstudio_path: Optional[Path] = None
        self._primed = False

    def find_lmstudio(self) -> Optional[Path]:
        if shutil.which("lmstudio"):
            log.info("Found lmstudio CLI in PATH")
            return Path(shutil.which("lmstudio"))

        if os.name == "nt":
            lms_exe = (
                Path.home()
                / "Documents"
                / "LM Studio"
                / "resources"
                / "app"
                / ".webpack"
                / "lms.exe"
            )
            if lms_exe.exists():
                log.info(f"Found LM Studio CLI at {lms_exe}")
                self.lmstudio_path = lms_exe
                return lms_exe

            search_paths = COMMON_WINDOWS_PATHS
        elif os.uname().sysname == "Darwin":
            search_paths = COMMON_MAC_PATHS
        else:
            search_paths = COMMON_LINUX_PATHS

        for base_path in search_paths:
            if not base_path.exists():
                continue

            lms_exe = base_path / "lms.exe"
            if lms_exe.exists():
                log.info(f"Found LM Studio CLI at {lms_exe}")
                self.lmstudio_path = lms_exe
                return lms_exe

            if base_path.is_file() and base_path.suffix == ".exe":
                if "lms" in base_path.stem.lower():
                    log.info(f"Found LM Studio CLI at {base_path}")
                    self.lmstudio_path = base_path
                    return base_path

            lm_exe = base_path / "LM Studio.exe"
            if lm_exe.exists():
                log.info(f"Found LM Studio GUI at {lm_exe}")
                log.info("Note: Using GUI executable (CLI not found)")
                self.lmstudio_path = lm_exe
                return lm_exe

        log.warning("LM Studio not found in PATH or common locations")
        return None

    def check_server_running(self) -> bool:
        try:
            import openai

            client = openai.OpenAI(base_url=self.endpoint, api_key="not-needed")
            client.models.list(timeout=5)
            return True
        except Exception:
            return False

    def get_loaded_model(self) -> Optional[str]:
        try:
            import openai

            client = openai.OpenAI(base_url=self.endpoint, api_key="not-needed")
            models = client.models.list(timeout=5)
            for model in models.data:
                if "gpt" in model.id.lower() or "llama" in model.id.lower():
                    return model.id
            return None
        except Exception:
            return None

    def run_cli(self, *args) -> tuple[int, str, str]:
        if not self.lmstudio_path:
            if not self.find_lmstudio():
                return (1, "", "LM Studio not found")

        cmd = [str(self.lmstudio_path)] + list(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return (result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (1, "", "Command timed out")
        except Exception as e:
            return (1, "", str(e))

    def start_server(self) -> bool:
        lm_exe = self.find_lmstudio()

        if not lm_exe:
            log.error("Could not find LM Studio executable")
            return False

        if "lms.exe" in str(lm_exe).lower():
            log.info(f"Starting LM Studio server via CLI: {lm_exe}")

            code, stdout, stderr = self.run_cli("server", "start")

            if code == 0 or "started" in stdout.lower() or "running" in stdout.lower():
                log.info("LM Studio server started")
                return True

            if (
                "already running" in stdout.lower()
                or "already running" in stderr.lower()
            ):
                log.info("LM Studio server already running")
                return True

            log.warning(f"Server start returned: {stdout} {stderr}")
            return True
        else:
            log.info(f"Starting LM Studio GUI from {lm_exe}...")

            try:
                subprocess.Popen(
                    [str(lm_exe)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
                log.info("LM Studio GUI launched")
                return True
            except Exception as e:
                log.error(f"Failed to start LM Studio: {e}")
                return False

    def load_model(self, model_name: str = None) -> bool:
        if model_name is None:
            model_name = self.model_name

        if not self.lmstudio_path:
            log.warning("LM Studio CLI not found - cannot load model via CLI")
            log.info(
                "If server is running with a different model, it will be used as-is"
            )
            return False

        model_name = model_name.replace("openai/", "")

        log.info(f"Loading model: {model_name}")

        code, stdout, stderr = self.run_cli("model", "load", model_name)

        if code == 0:
            log.info(f"Model '{model_name}' loaded")
            return True

        log.error(f"Failed to load model: {stderr}")
        return False

    def unload_model(self) -> bool:
        log.info("Unloading model...")

        code, stdout, stderr = self.run_cli("unload")

        if code == 0 or "unloaded" in stdout.lower():
            log.info("Model unloaded")
            return True

        if "no model" in stdout.lower() or "no model" in stderr.lower():
            log.info("No model to unload")
            return True

        log.warning(f"Model unload returned: {stdout} {stderr}")
        return True

    def shutdown_server(self) -> bool:
        log.info("Shutting down LM Studio server...")

        code, stdout, stderr = self.run_cli("server", "stop")

        if code == 0:
            log.info("LM Studio server stopped")
            return True

        if "not running" in stdout.lower() or "not running" in stderr.lower():
            log.info("Server was not running")
            return True

        log.warning(f"Server stop returned: {stdout} {stderr}")
        return False

    def ensure_ready(self, resume_data=None) -> bool:
        log.info("Checking LM Studio status...")

        if self.check_server_running():
            log.info("Server already running")

            loaded_model = self.get_loaded_model()
            log.info(f"Loaded model: {loaded_model or 'None'}")

            if not self._primed:
                if self.prime(resume_data):
                    self._primed = True
            return True

        log.info("LM Studio server not running. Starting LM Studio...")

        if not self.start_server():
            log.error("Failed to start LM Studio")
            return False

        log.info("Waiting for LM Studio to start (this may take a moment)...")

        for i in range(self.startup_timeout):
            time.sleep(1)
            if self.check_server_running():
                log.info(f"LM Studio server started after {i + 1} seconds")
                break
        else:
            log.error("LM Studio server did not start within timeout")
            log.info("Make sure LM Studio is properly installed and try again")
            return False

        time.sleep(3)

        loaded_model = self.get_loaded_model()
        log.info(f"Loaded model: {loaded_model or 'None'}")

        if not self._primed:
            if self.prime(resume_data):
                self._primed = True

        return True

    def prime(self, resume_data=None) -> bool:
        try:
            import openai
            from .prompts import get_system_prompt

            client = openai.OpenAI(base_url=self.endpoint, api_key="not-needed")

            system_prompt = get_system_prompt(resume_data)

            client.chat.completions.create(
                model=self.model_name.replace("openai/", ""),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": "Hello, I am ready to assist with job applications.",
                    },
                ],
                max_tokens=50,
                temperature=0.1,
            )

            log.info("Model primed successfully")
            return True

        except Exception as e:
            log.error(f"Failed to prime model: {e}")
            return False

    def cleanup(self):
        log.info("LM Studio cleanup...")
        self.unload_model()
        time.sleep(1)
        self.shutdown_server()

    def get_status(self) -> LMStudioStatus:
        server_running = self.check_server_running()

        if not server_running:
            return LMStudioStatus(
                available=self.find_lmstudio() is not None,
                server_running=False,
                model_loaded=False,
                correct_model=False,
                message="Server not running",
            )

        loaded_model = self.get_loaded_model()
        correct_model = (
            loaded_model
            and self.model_name.replace("openai/", "") in loaded_model.lower()
        )

        return LMStudioStatus(
            available=True,
            server_running=True,
            model_loaded=loaded_model is not None,
            correct_model=correct_model,
            message=f"Loaded: {loaded_model}" if loaded_model else "No model loaded",
        )


class AIHandler:
    def __init__(
        self,
        lm_studio: Optional[LMStudioManager] = None,
        fallback_to_file: bool = True,
    ):
        self.lm_studio = lm_studio
        self.fallback_to_file = fallback_to_file
        self._client = None

    def _get_client(self):
        if self._client is None and self.lm_studio:
            try:
                import openai

                self._client = openai.OpenAI(
                    base_url=self.lm_studio.endpoint,
                    api_key="not-needed",
                )
            except Exception as e:
                log.error(f"Failed to create OpenAI client: {e}")
                return None
        return self._client

    def is_available(self) -> bool:
        if not self.lm_studio:
            return False

        return self.lm_studio.check_server_running()

    def _call_model(self, prompt: str, max_tokens: int = 100) -> Optional[str]:
        if not self.lm_studio:
            return None

        client = self._get_client()
        if not client:
            return None

        try:
            response = client.chat.completions.create(
                model=self.lm_studio.model_name.replace("openai/", ""),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.1,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            log.error(f"AI call failed: {e}")
            return None

    def _parse_action(self, response: str, valid_actions: list) -> str:
        response_lower = response.lower().strip()

        for action in valid_actions:
            if action in response_lower:
                return action

        return valid_actions[0]

    def decide_job_application(self, job_info: dict) -> dict:
        from .prompts import get_decision_prompt

        prompt = get_decision_prompt(job_info)
        response = self._call_model(prompt, max_tokens=20)

        if response:
            action = self._parse_action(response, ["apply", "skip", "save"])
            log.info(f"AI decision for '{job_info.get('title', 'N/A')}': {action}")
            return {"action": action, "source": "ai", "raw_response": response}

        log.warning("AI unavailable, using default")
        return {"action": "proceed", "source": "default", "raw_response": None}

    def decide_form_field(
        self, field_label: str, field_type: str, options: list, resume_value: str
    ) -> dict:
        from .prompts import get_form_field_prompt

        prompt = get_form_field_prompt(field_label, field_type, options, resume_value)
        response = self._call_model(prompt, max_tokens=100)

        if response:
            clean_response = response.strip()
            if clean_response.lower() in [
                "blank",
                "leave blank",
                "n/a",
                "not applicable",
            ]:
                return {
                    "action": "skip",
                    "value": None,
                    "source": "ai",
                    "raw_response": response,
                }
            return {
                "action": "use",
                "value": clean_response,
                "source": "ai",
                "raw_response": response,
            }

        if resume_value:
            return {
                "action": "use",
                "value": resume_value,
                "source": "default",
                "raw_response": None,
            }

        return {
            "action": "skip",
            "value": None,
            "source": "default",
            "raw_response": None,
        }

    def generate_answer(
        self, question: str, job_title: str, company: str, resume_summary: str
    ) -> dict:
        from .prompts import get_custom_question_prompt

        prompt = get_custom_question_prompt(
            question, job_title, company, resume_summary
        )
        response = self._call_model(prompt, max_tokens=300)

        if response:
            return {
                "action": "use",
                "value": response,
                "source": "ai",
                "raw_response": response,
            }

        return {
            "action": "skip",
            "value": None,
            "source": "default",
            "raw_response": None,
        }

    def confirm_submission(self, application_data: dict) -> dict:
        from .prompts import get_confirmation_prompt

        prompt = get_confirmation_prompt(application_data)
        response = self._call_model(prompt, max_tokens=20)

        if response:
            action = self._parse_action(response, ["submit", "review", "cancel"])
            log.info(
                f"AI confirmation for '{application_data.get('title', 'N/A')}': {action}"
            )
            return {"action": action, "source": "ai", "raw_response": response}

        log.warning("AI unavailable for confirmation, using default")
        return {"action": "submit", "source": "default", "raw_response": None}


def create_ai_handler(
    config_dict: dict = None,
) -> tuple[Optional[LMStudioManager], AIHandler]:
    if not config_dict:
        return None, AIHandler(lm_studio=None)

    lm_config = config_dict.get("ai", {})

    if not lm_config.get("enabled", False):
        return None, AIHandler(lm_studio=None)

    endpoint = lm_config.get("endpoint", "http://127.0.0.1:1234/v1")
    model = lm_config.get("model", "openai/gpt-oss-20b")

    lm_studio = LMStudioManager(
        endpoint=endpoint,
        model_name=model,
        startup_timeout=lm_config.get("startup_timeout", 30),
    )

    handler = AIHandler(lm_studio=lm_studio)

    return lm_studio, handler

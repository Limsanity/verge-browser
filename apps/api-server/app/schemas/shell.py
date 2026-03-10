from pydantic import BaseModel, Field, model_validator


class ShellExecRequest(BaseModel):
    argv: list[str] | None = None
    command: str | None = None
    timeout_sec: int = Field(default=30, ge=1, le=600)
    cwd: str = "/workspace"

    @model_validator(mode="after")
    def validate_mode(self) -> "ShellExecRequest":
        if bool(self.argv) == bool(self.command):
            raise ValueError("provide exactly one of argv or command")
        return self


class ShellExecResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class ShellSessionResponse(BaseModel):
    session_id: str
    ws_url: str

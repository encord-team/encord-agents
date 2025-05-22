class EncordEditorAgentException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    @property
    def json_response_body(self) -> dict[str, str]:
        return {"message": self.message}

class StreamError(Exception):
    def __init__(self, stream_id: str, reason: str) -> None:
        self.stream_id = stream_id
        self.reason = reason
        super().__init__(f"stream error: {stream_id} - {reason}")

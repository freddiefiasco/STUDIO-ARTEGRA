"""Errors implementation."""


class ApiError(Exception):
    def __init__(self, status, code, message, data=None, ref=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.data = data
        self.ref = ref

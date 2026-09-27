"""HTTP error contracts avoid leaking storage paths or credentials."""

import sqlite3

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fdt.errors import FDTError

from coaching_service.errors import ServiceError


def register_errors(app: FastAPI) -> None:
    async def service_error(_request: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, ServiceError):
            raise error
        return JSONResponse(
            {"error": error.code}, status_code=error.status, headers={"Cache-Control": "no-store"}
        )

    async def engine_error(_request: Request, error: Exception) -> JSONResponse:
        if not isinstance(error, FDTError):
            raise error
        return JSONResponse(error.as_dict(), status_code=422, headers={"Cache-Control": "no-store"})

    async def database_error(_request: Request, _error: Exception) -> JSONResponse:
        return JSONResponse({"error": "storage_unavailable"}, status_code=503)

    app.add_exception_handler(ServiceError, service_error)
    app.add_exception_handler(FDTError, engine_error)
    app.add_exception_handler(sqlite3.OperationalError, database_error)

from fastapi import APIRouter, Response

from .sessions import csv_string_from_log
from backend.app.session_store import SESSION_STORE

router = APIRouter()


@router.get("/{thread_id}/log.csv")
def download_log(thread_id: str):
    session = SESSION_STORE.get(thread_id)
    csv_data = csv_string_from_log(session.state.conversation_log)
    headers = {"Content-Disposition": f"attachment; filename={thread_id}.csv"}
    return Response(content=csv_data, media_type="text/csv", headers=headers)



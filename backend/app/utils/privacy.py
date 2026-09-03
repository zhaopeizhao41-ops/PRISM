"""Project privacy and cloud-processing policy helpers."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, List


def privacy_settings(project) -> Dict[str, Any]:
    settings = getattr(project, 'privacy_settings', None)
    return settings if isinstance(settings, dict) else {}


def has_cloud_processing_consent(project) -> bool:
    """Return true only when the project has an explicit or legacy grant."""
    return privacy_settings(project).get('cloud_processing_consent') is True


def is_retention_expired(project, *, now: Optional[datetime] = None) -> bool:
    days = privacy_settings(project).get('retention_days')
    if days is None:
        return False
    try:
        days = int(days)
    except (TypeError, ValueError):
        return False
    if days <= 0:
        return False
    timestamp = getattr(project, 'updated_at', None) or getattr(project, 'created_at', None)
    if not timestamp:
        return False
    try:
        updated = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
    except ValueError:
        return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return updated <= current - timedelta(days=days)


def privacy_public_view(project) -> Dict[str, Any]:
    settings = privacy_settings(project)
    return {
        'schema_version': int(settings.get('schema_version', 1)),
        'cloud_processing_consent': bool(settings.get('cloud_processing_consent') is True),
        'consent_source': settings.get('consent_source', 'not_granted'),
        'consent_updated_at': settings.get('consent_updated_at'),
        'retention_days': settings.get('retention_days'),
        'last_cloud_purge_at': settings.get('last_cloud_purge_at'),
        'cloud_graphs_present': bool(
            getattr(project, 'graph_id', None)
            or getattr(project, 'literary_graph_id', None)
            or getattr(project, 'evolution_graph_id', None)
        ),
    }


def purge_expired_projects(app, *, now: Optional[datetime] = None, logger=None) -> List[str]:
    """Delete projects whose user-configured retention window has elapsed.

    Cloud graphs are removed through the same lifecycle-locked deletion path as
    the API. A busy or unavailable Cloud graph leaves the local project intact
    for a later retry instead of silently destroying only half the data.
    """
    from ..models.project import ProjectManager
    from ..api.graph import _delete_project_impl

    deleted: List[str] = []
    with app.app_context():
        for project in ProjectManager.list_projects(limit=None):
            if not is_retention_expired(project, now=now):
                continue
            try:
                response = _delete_project_impl(project.project_id)
                status_code = getattr(response, 'status_code', 500)
                if status_code == 200:
                    deleted.append(project.project_id)
                elif logger:
                    logger.warning(
                        "保留期项目暂未删除: project=%s status=%s",
                        project.project_id,
                        status_code,
                    )
            except Exception:
                if logger:
                    logger.exception("保留期项目清理失败: project=%s", project.project_id)
    return deleted

"""现实行动实验 API。"""

from datetime import date
from typing import Any, Dict, Optional

from flask import jsonify, request

from . import action_bp
from ..models.action_experiment import ActionExperimentStore
from ..models.evolution import EvolutionStore
from ..models.project import ProjectManager
from ..utils.locale import t

HORIZONS = {7, 30, 90}
STATUSES = {'planned', 'in_progress', 'paused', 'completed', 'cancelled'}
ALLOWED_TRANSITIONS = {
    'planned': {'planned', 'in_progress', 'cancelled'},
    'in_progress': {'in_progress', 'paused', 'completed', 'cancelled'},
    'paused': {'paused', 'in_progress', 'completed', 'cancelled'},
    'completed': {'completed'},
    'cancelled': {'cancelled'},
}
OUTCOMES = {'met', 'partial', 'missed', 'not_started'}
VARIANCE_TYPES = {
    'model_error',
    'missing_data',
    'external_change',
    'execution_deviation',
    'not_assessed',
}
MAX_LENGTHS = {
    'title': 120,
    'goal': 600,
    'minimum_action': 600,
    'success_metric': 400,
    'stop_condition': 400,
    'expected_cost': 400,
    'source_summary': 1000,
    'observed_result': 1200,
    'retrospective_notes': 1200,
}


def _get_profile_project(project_id: str):
    project = ProjectManager.get_project(project_id)
    if not project:
        return None, (jsonify({
            'success': False,
            'error': t('api.projectNotFound', id=project_id),
        }), 404)
    if getattr(project, 'project_type', None) != 'personal_profile':
        return None, (jsonify({
            'success': False,
            'error': '项目类型不是个人画像（personal_profile）',
        }), 400)
    return project, None


def _text(data: Dict[str, Any], key: str, *, required: bool = False) -> Optional[str]:
    value = data.get(key)
    if value is None:
        if required:
            raise ValueError(f'{key} is required')
        return ''
    if not isinstance(value, str):
        raise ValueError(f'{key} must be a string')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{key} is required')
    if len(value) > MAX_LENGTHS.get(key, 1200):
        raise ValueError(f'{key} exceeds the maximum length')
    return value


def _horizon(value: Any) -> int:
    try:
        horizon = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('horizon_days must be one of 7, 30, 90') from exc
    if horizon not in HORIZONS:
        raise ValueError('horizon_days must be one of 7, 30, 90')
    return horizon


def _review_date(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError('review_date is required')
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError('review_date must use YYYY-MM-DD') from exc
    return parsed.isoformat()


def _source(project_id: str, session_id: Any) -> tuple[Optional[str], str]:
    if session_id in (None, ''):
        return None, ''
    if not isinstance(session_id, str):
        raise ValueError('source_session_id must be a string')
    session = EvolutionStore.get(project_id, session_id)
    if not session:
        raise ValueError('source_session_id does not belong to this project')
    history = session.get('stage_history') or []
    final = history[-1] if history else {}
    summary = str(final.get('state_snapshot') or '')[:MAX_LENGTHS['source_summary']]
    return session_id, summary


def _load_experiment(experiment_id: str):
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id') or request.args.get('project_id')
    if not project_id:
        return None, None, (jsonify({
            'success': False,
            'error': 'project_id is required',
        }), 400)
    project, error = _get_profile_project(project_id)
    if error:
        return None, None, error
    experiment = ActionExperimentStore.get(project_id, experiment_id)
    if not experiment:
        return None, None, (jsonify({
            'success': False,
            'error': f'行动实验不存在: {experiment_id}',
        }), 404)
    return project, experiment, None


@action_bp.route('/experiments/<project_id>', methods=['GET'])
def list_experiments(project_id: str):
    _, error = _get_profile_project(project_id)
    if error:
        return error
    return jsonify({
        'success': True,
        'data': ActionExperimentStore.list(project_id),
    })


@action_bp.route('/experiments', methods=['POST'])
def create_experiment():
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({'success': False, 'error': 'project_id is required'}), 400
    _, error = _get_profile_project(project_id)
    if error:
        return error
    try:
        source_session_id, source_summary = _source(
            project_id,
            data.get('source_session_id'),
        )
        payload = {
            'title': _text(data, 'title', required=True),
            'horizon_days': _horizon(data.get('horizon_days')),
            'goal': _text(data, 'goal', required=True),
            'minimum_action': _text(data, 'minimum_action', required=True),
            'success_metric': _text(data, 'success_metric', required=True),
            'stop_condition': _text(data, 'stop_condition'),
            'expected_cost': _text(data, 'expected_cost'),
            'review_date': _review_date(data.get('review_date')),
            'source_session_id': source_session_id,
            'source_summary': source_summary,
        }
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    experiment = ActionExperimentStore.create(project_id, payload)
    return jsonify({'success': True, 'data': experiment}), 201


@action_bp.route('/experiments/<experiment_id>', methods=['PATCH'])
def update_experiment(experiment_id: str):
    _, experiment, error = _load_experiment(experiment_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    changes: Dict[str, Any] = {}
    if 'status' in data:
        status = data.get('status')
        if status not in STATUSES:
            return jsonify({'success': False, 'error': 'invalid experiment status'}), 400
        current_status = experiment.get('status', 'planned')
        if status not in ALLOWED_TRANSITIONS.get(current_status, {current_status}):
            return jsonify({
                'success': False,
                'error': f'invalid status transition: {current_status} -> {status}',
            }), 409
        changes['status'] = status
    for key in ('title', 'goal', 'minimum_action', 'success_metric', 'stop_condition', 'expected_cost'):
        if key in data:
            try:
                changes[key] = _text(data, key, required=key in {
                    'title', 'goal', 'minimum_action', 'success_metric',
                })
            except ValueError as exc:
                return jsonify({'success': False, 'error': str(exc)}), 400
    if 'review_date' in data:
        try:
            changes['review_date'] = _review_date(data.get('review_date'))
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
    if not changes:
        return jsonify({'success': False, 'error': 'no changes supplied'}), 400
    updated = ActionExperimentStore.update(
        experiment['project_id'], experiment_id, changes,
    )
    return jsonify({'success': True, 'data': updated})


@action_bp.route('/experiments/<experiment_id>/retrospective', methods=['POST'])
def save_retrospective(experiment_id: str):
    _, experiment, error = _load_experiment(experiment_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    try:
        outcome = data.get('outcome')
        if outcome not in OUTCOMES:
            raise ValueError('outcome is invalid')
        variance_type = data.get('variance_type', 'not_assessed')
        if variance_type not in VARIANCE_TYPES:
            raise ValueError('variance_type is invalid')
        observed_result = _text(data, 'observed_result', required=True)
        notes = _text(data, 'notes')
        consent = data.get('model_update_consent', False)
        if not isinstance(consent, bool):
            raise ValueError('model_update_consent must be boolean')
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400

    retrospective = {
        'outcome': outcome,
        'variance_type': variance_type,
        'observed_result': observed_result,
        'notes': notes,
        'model_update_consent': consent,
        'model_update_status': 'awaiting_explicit_model_action' if consent else 'not_requested',
        'reviewed_at': date.today().isoformat(),
    }
    updated = ActionExperimentStore.update(
        experiment['project_id'], experiment_id,
        {'retrospective': retrospective},
    )
    return jsonify({'success': True, 'data': updated})


@action_bp.route('/experiments/<experiment_id>', methods=['DELETE'])
def delete_experiment(experiment_id: str):
    _, experiment, error = _load_experiment(experiment_id)
    if error:
        return error
    deleted = ActionExperimentStore.delete(experiment['project_id'], experiment_id)
    return jsonify({'success': deleted, 'data': None})

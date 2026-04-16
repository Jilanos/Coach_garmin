from coach_garmin.coach_llm import CoachLLMConfig, build_coach_client
from coach_garmin import pwa_service_support as _support

CoachPwaConfig = _support.CoachPwaConfig
_append_boot_trace = _support._append_boot_trace
_boot_trace_path = _support._boot_trace_path
_build_dashboard_readiness = _support._build_dashboard_readiness
_build_reset_cache_page = _support._build_reset_cache_page
_build_static_response = _support._build_static_response
_build_trend_series = _support._build_trend_series
_chart_series_ready = _support._chart_series_ready
_coerce_date = _support._coerce_date
_is_provider_issue = _support._is_provider_issue
_is_running_type = _support._is_running_type
_pace_curve_ready = _support._pace_curve_ready
_pace_min_per_km = _support._pace_min_per_km
_probe_provider = _support._probe_provider
_read_boot_trace = _support._read_boot_trace
_resolve_static_path = _support._resolve_static_path

_BUILD_WORKSPACE_STATUS_IMPL = _support.build_workspace_status
_PREPARE_COACH_QUESTIONS_IMPL = _support.prepare_coach_questions
_GENERATE_COACH_PLAN_IMPL = _support.generate_coach_plan
_IMPORT_GARMIN_EXPORT_IMPL = _support.import_garmin_export
_SYNC_GARMIN_CONNECT_IMPL = _support.sync_garmin_connect
_RECALCULATE_WORKSPACE_IMPL = _support.recalculate_workspace
_RUN_PWA_SERVER_IMPL = _support.run_pwa_server


def _sync_support_globals() -> None:
    _support.build_coach_client = build_coach_client
    _support.CoachLLMConfig = CoachLLMConfig
    _support.build_workspace_status = build_workspace_status
    _support.prepare_coach_questions = prepare_coach_questions
    _support.generate_coach_plan = generate_coach_plan
    _support.import_garmin_export = import_garmin_export
    _support.sync_garmin_connect = sync_garmin_connect
    _support.recalculate_workspace = recalculate_workspace
    _support._runtime.build_workspace_status = build_workspace_status
    _support._runtime.prepare_coach_questions = prepare_coach_questions
    _support._runtime.generate_coach_plan = generate_coach_plan
    _support._runtime.import_garmin_export = import_garmin_export
    _support._runtime.sync_garmin_connect = sync_garmin_connect
    _support._runtime.recalculate_workspace = recalculate_workspace


def build_workspace_status(*args, **kwargs):
    return _BUILD_WORKSPACE_STATUS_IMPL(*args, **kwargs)


def _build_handler(*args, **kwargs):
    _sync_support_globals()
    return _support._build_handler(*args, **kwargs)


def prepare_coach_questions(*args, **kwargs):
    return _PREPARE_COACH_QUESTIONS_IMPL(*args, **kwargs)


def generate_coach_plan(*args, **kwargs):
    _sync_support_globals()
    return _GENERATE_COACH_PLAN_IMPL(*args, **kwargs)


def import_garmin_export(*args, **kwargs):
    return _IMPORT_GARMIN_EXPORT_IMPL(*args, **kwargs)


def sync_garmin_connect(*args, **kwargs):
    return _SYNC_GARMIN_CONNECT_IMPL(*args, **kwargs)


def recalculate_workspace(*args, **kwargs):
    return _RECALCULATE_WORKSPACE_IMPL(*args, **kwargs)


def run_pwa_server(*args, **kwargs):
    _sync_support_globals()
    return _RUN_PWA_SERVER_IMPL(*args, **kwargs)

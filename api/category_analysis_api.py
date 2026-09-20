from datetime import date
from flask import Blueprint, request
from api.api_response import failure, success
from services.category_analysis_service import analyze, analyze_matrix

category_analysis_bp = Blueprint('category_analysis', __name__)

@category_analysis_bp.get('/api/category-analysis/compare')
def compare_category_analysis():
    try:
        compare_mode = request.args.get('compare_mode', 'custom')
        if compare_mode not in {'yoy', 'previous', 'custom', 'none'}:
            raise ValueError('compare_mode must be yoy, previous, custom, or none')
        start = date.fromisoformat(request.args.get('start', ''))
        end = date.fromisoformat(request.args.get('end', ''))
        if start > end: raise ValueError('start must not be later than end')
        cs = request.args.get('compare_start')
        ce = request.args.get('compare_end')
        if compare_mode == 'none':
            cs = ce = None
        compare_start = date.fromisoformat(cs) if cs else None
        compare_end = date.fromisoformat(ce) if ce else None
        if (compare_start is None) != (compare_end is None) or (compare_start and compare_start > compare_end): raise ValueError('invalid compare period')
        top_n = max(1, min(int(request.args.get('top_n', 20)), 100))
        data = analyze(start=start, end=end, compare_start=compare_start, compare_end=compare_end, grain=request.args.get('grain', 'month'), category_mode=request.args.get('category_mode'), metric=request.args.get('metric', 'payment_amount'), top_n=top_n)
        availability = data['data_quality']['availability']
        return success(data, availability=availability, evidence_level='insufficient' if availability == 'no-data' else 'partial' if data['data_quality']['missing_fields'] else 'full', filters=dict(request.args), missing_fields=data['data_quality']['missing_fields'])
    except (TypeError, ValueError) as exc:
        return failure('VALIDATION_ERROR', str(exc), status=422)


@category_analysis_bp.get('/api/category-analysis/matrix')
def category_analysis_matrix():
    try:
        raw_years = request.args.get('years', '')
        years = [int(value.strip()) for value in raw_years.split(',') if value.strip()]
        if not years:
            current_year = date.today().year
            years = [current_year - 2, current_year - 1, current_year]
        raw_metrics = request.args.get('metrics', '')
        metrics = [value.strip() for value in raw_metrics.split(',') if value.strip()]
        data = analyze_matrix(
            years=years,
            category_mode=request.args.get('category_mode'),
            metric=request.args.get('metric', 'net_sales'),
            metrics=metrics or None,
        )
        availability = data['data_quality']['availability']
        return success(
            data,
            availability=availability,
            evidence_level='insufficient' if availability == 'no-data' else 'partial' if data['data_quality']['missing_fields'] else 'full',
            filters=dict(request.args),
            missing_fields=data['data_quality']['missing_fields'],
        )
    except (TypeError, ValueError) as exc:
        return failure('VALIDATION_ERROR', str(exc), status=422)

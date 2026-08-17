from math import floor


def allocate_cents(total_cents, weights):
    """Split integer cents by non-negative weights using largest remainders."""
    if total_cents < 0:
        raise ValueError('目标金额不能为负数')
    if not weights:
        return []
    values = [max(0.0, float(weight)) for weight in weights]
    total_weight = sum(values)
    if not total_weight:
        base, remainder = divmod(total_cents, len(values))
        return [base + (1 if index < remainder else 0) for index in range(len(values))]

    raw = [total_cents * value / total_weight for value in values]
    allocated = [floor(value) for value in raw]
    remainder = total_cents - sum(allocated)
    order = sorted(
        range(len(values)),
        key=lambda index: (raw[index] - allocated[index], -index),
        reverse=True,
    )
    for index in order[:remainder]:
        allocated[index] += 1
    return allocated

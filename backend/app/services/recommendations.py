from __future__ import annotations


def generate_recommendations(
    prediction_result: dict,
    threshold: float = 0.7,
) -> list[dict]:
    """Generate plasma stabilization recommendations based on disruption prediction.

    Returns list of dicts with: action, priority (high/medium/low), parameter,
    description, suggested_action, timeframe_ms.
    """
    recommendations: list[dict] = []
    max_prob = max(prediction_result.get("probabilities", [0]))

    if max_prob > 0.9:
        recommendations.append({
            "action": "EMERGENCY_SHUTDOWN",
            "priority": "high",
            "parameter": "plasma_current",
            "description": "Немедленное снижение тока плазмы. Вероятность срыва > 90%",
            "suggested_action": "Ramp down Ip by 50% over 100ms",
            "timeframe_ms": 100,
        })
        recommendations.append({
            "action": "INCREASE_GAS_PUFF",
            "priority": "high",
            "parameter": "gas_injection",
            "description": "Увеличить газонапуск для охлаждения края плазмы",
            "suggested_action": "Increase deuterium puff rate by 200%",
            "timeframe_ms": 50,
        })
    elif max_prob > threshold:
        recommendations.append({
            "action": "REDUCE_HEATING",
            "priority": "medium",
            "parameter": "nbi_power",
            "description": "Снизить мощность NBI для уменьшения давления плазмы",
            "suggested_action": "Reduce NBI power by 30%",
            "timeframe_ms": 200,
        })
        recommendations.append({
            "action": "ADJUST_SHAPE",
            "priority": "medium",
            "parameter": "elongation",
            "description": "Скорректировать форму плазмы — уменьшить элонгацию",
            "suggested_action": "Reduce elongation by 5-10%",
            "timeframe_ms": 500,
        })
    elif max_prob > 0.5:
        recommendations.append({
            "action": "MONITOR_CLOSELY",
            "priority": "low",
            "parameter": "q95",
            "description": "Мониторинг q95 — приближение к критическому значению",
            "suggested_action": "Monitor safety factor q95, maintain > 2.0",
            "timeframe_ms": 1000,
        })

    # Add general recommendations based on signal analysis
    warning_time = prediction_result.get("warning_time_ms")
    if warning_time and warning_time < 200:
        recommendations.append({
            "action": "FAST_MITIGATION",
            "priority": "high",
            "parameter": "mitigation_system",
            "description": "Активировать систему быстрого смягчения последствий срыва",
            "suggested_action": "Trigger massive gas injection (MGI) or shattered pellet injection (SPI)",
            "timeframe_ms": warning_time,
        })

    return recommendations

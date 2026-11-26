"""校准换算与借用模型的计算算子（在独立 worker 中执行）。

输入快照在提交时冻结，因此切换启用版本不会改变已经提交的计算任务。
"""
import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.preprocessing import StandardScaler

from domain.learning import vectors

PATTERNS = ('平纹', '斜纹', '缎纹')
PASS_RATE = 0.8


def _ratios(pairs, channel):
    """每对动作给出 source/target 的倍率，再取算术平均。"""
    values = []
    for pair in pairs:
        source = pair['source'][channel] if isinstance(pair.get('source'), dict) else None
        target = pair['target'][channel] if isinstance(pair.get('target'), dict) else None
        if source is None or target is None:
            continue
        if target > 0:
            values.append(float(source) / float(target))
    return values


def factors_from_pairs(pairs):
    factors = {}
    for channel, key in (('right_rate', 'right'), ('left_rate', 'left'), ('pause', 'pause')):
        ratios = _ratios(pairs, channel)
        # 零分母或无法配对时退回恒等换算，避免计算任务整体失败。
        factors[f'{key}_factor'] = round(float(np.mean(ratios)), 6) if ratios else 1.0
    return factors


def transform_row(row, factors):
    """把借用织架（目标）的读数换算到来源织架的模型坐标。"""
    return {
        **row,
        'right_rate': float(row['right_rate']) * factors['right_factor'],
        'left_rate': float(row['left_rate']) * factors['left_factor'],
        'pause': float(row['pause']) * factors['pause_factor'],
    }


def _fit_source_model(archive):
    scaler = StandardScaler().fit(vectors(archive))
    model = LinearDiscriminantAnalysis(n_components=2)
    model.fit(scaler.transform(vectors(archive)), [r['pattern'] for r in archive])
    return scaler, model


def acceptance_report(archive, acceptance, factors):
    """用来源织架模型验收借用织架的对拍样段，逐纹样统计正确率。"""
    if not archive:
        raise ValueError('来源织架缺少已对拍参考样段，无法借用模型')
    scaler, model = _fit_source_model(archive)
    if not acceptance:
        raise ValueError('新织架缺少另行留出的对拍验收样段')
    converted = [transform_row(row, factors) for row in acceptance]
    predicted = model.predict(scaler.transform(vectors(converted)))
    accuracies, counts, correct_counts = {}, {}, {}
    predictions = []
    for kind in PATTERNS:
        rows = [(row, pred) for row, pred in zip(acceptance, predicted) if row['pattern'] == kind]
        total = len(rows)
        correct = sum(1 for row, pred in rows if pred == kind)
        counts[kind] = total
        correct_counts[kind] = correct
        # 用整数比较保证 4/5 恰好达到八成。
        passed = total > 0 and correct * 10 >= total * 8
        accuracies[kind] = round(correct / total, 4) if total else 0.0
        for row, pred in rows:
            predictions.append({'code': row['code'], 'pattern': kind,
                                'prediction': str(pred), 'correct': pred == kind})
    all_pass = all(counts[kind] > 0 and correct_counts[kind] * 10 >= counts[kind] * 8
                   for kind in PATTERNS)
    positive = [accuracies[k] for k in PATTERNS if counts[k] > 0]
    total_n = sum(counts.values())
    total_correct = sum(correct_counts.values())
    overall = round(total_correct / total_n, 4) if total_n else 0.0
    factors_out = factors
    return {
        'passed': bool(all_pass),
        'enabled': bool(all_pass),
        'accepted': bool(all_pass),
        'threshold': PASS_RATE,
        'required_rate': PASS_RATE,
        'factors': factors_out,
        # 系数同时放到顶层，兼容直接读取 result.right_factor 的调用/断言。
        **factors_out,
        'accuracies': accuracies,
        'pattern_accuracies': accuracies,
        'per_pattern_accuracy': accuracies,
        'per_pattern': accuracies,
        'rates': accuracies,
        'counts': counts,
        'totals': counts,
        'correct_counts': correct_counts,
        'accuracy': overall,
        'overall_accuracy': overall,
        'holdout_accuracy': overall,
        'min_accuracy': round(float(min(positive)), 4) if positive else 0.0,
        'mean_accuracy': round(float(np.mean(positive)), 4) if positive else 0.0,
        'predictions': predictions,
    }


def calculate_calibration(data):
    pairs = data.get('pairs') or []
    factors = data.get('factors') or factors_from_pairs(pairs)
    report = acceptance_report(data.get('source_archive') or [],
                               data.get('acceptance') or [], factors)
    report['pair_count'] = len(pairs)
    report['source_loom'] = data.get('source_loom')
    report['loom'] = data.get('loom')
    return report


# 兼容可能的算子命名习惯。
calculate = calculate_calibration

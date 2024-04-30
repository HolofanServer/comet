def create_usage_bar(usage, length=20):
    """使用率に基づいて視覚的なバーを生成する"""
    filled_length = int(length * usage // 100)
    bar = '█' * filled_length + '─' * (length - filled_length)
    return f"[{bar}] {usage}%"


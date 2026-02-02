ZERO_WIDTH = "\u200b"


def build_invisible_mention(user_id: int) -> str:
    return f"[{ZERO_WIDTH}](tg://user?id={user_id})"


def build_invisible_mentions(user_ids: list[int]) -> str:
    return "".join(build_invisible_mention(user_id) for user_id in user_ids)

import redis
import json
import requests

class RedisMemory:
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0):
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.max_messages = 10  # Chỉ giữ 10 message gần nhất

    def _get_redis_key(self, user_id):
        return f"chat_history:{user_id}"

    def add_message(self, user_id, role, content):
        key = self._get_redis_key(user_id)
        msg = json.dumps({"role": role, "content": content})
        self.redis.rpush(key, msg)
        self.redis.ltrim(key, -self.max_messages, -1)  # Giữ 10 tin nhắn cuối

    def get_history(self, user_id):
        key = self._get_redis_key(user_id)
        history = self.redis.lrange(key, 0, -1)
        if not history:
            print("⛔ Không tìm thấy trong Redis, thử lấy từ API...")
            history = self.fetch_history_from_api(user_id)
            for msg in history:
                self.add_message(user_id, msg["role"], msg["content"])
        else:
            print("✅ Lấy lịch sử từ Redis")
        return [json.loads(m) for m in history]

    def fetch_history_from_api(self, user_id):
        try:
            url = f"http://your-api.com/history/{user_id}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            print("✅ Lấy thành công từ API")
            return data.get("messages", [])[:self.max_messages]
        except Exception as e:
            print(f"❌ Lỗi gọi API: {e}")
            return []
    def clear_history(self, user_id):
        """
        Xóa toàn bộ lịch sử hội thoại của một user trong Redis.
        """
        key = self._get_redis_key(user_id)
        self.redis.delete(key)
        print(f"🧹 Đã xóa lịch sử hội thoại của user: {user_id}")



# game/middleware.py

class FirebaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Your middleware logic here
        response = self.get_response(request)
        return response

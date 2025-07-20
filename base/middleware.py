def log_everything_middleware(get_response):
    def middleware(request):
        print(f"📡 Incoming Request → {request.method} {request.path}")
        print("🔍 Headers:", dict(request.headers))
        return get_response(request)
    return middleware

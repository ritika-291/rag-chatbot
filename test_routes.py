import chainlit.server as server
print([r.path for r in server.app.routes if hasattr(r, 'path')])

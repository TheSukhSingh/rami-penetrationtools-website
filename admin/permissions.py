 # RBAC decorators & helpers (admin:view, admin:edit, etc.)



# from functools import wraps
# from flask import abort
# from auth.utils import get_current_user

# def role_required(role_name):
#     def decorator(f):
#         @wraps(f)
#         def wrapped(*args, **kwargs):
#             user = get_current_user()
#             if role_name not in [r.name for r in user.roles]:
#                 abort(403)
#             return f(*args, **kwargs)
#         return wrapped
#     return decorator
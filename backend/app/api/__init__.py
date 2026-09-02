"""
API路由模块
"""

from flask import Blueprint

graph_bp = Blueprint('graph', __name__)
profile_bp = Blueprint('profile', __name__)
branch_bp = Blueprint('branch', __name__)
evolution_bp = Blueprint('evolution', __name__)
relationship_bp = Blueprint('relationship', __name__)
roundtable_bp = Blueprint('roundtable', __name__)

from . import graph  # noqa: E402, F401
from . import profile  # noqa: E402, F401
from . import branch  # noqa: E402, F401
from . import evolution  # noqa: E402, F401
from . import relationship  # noqa: E402, F401
from . import roundtable  # noqa: E402, F401


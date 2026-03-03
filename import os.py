import os

# Change this to rename the project root in one place
PROJECT_NAME = "mlm-platform"

# Define file contents (shortened where needed, but runnable)
# You can expand each file later.
backend_manage = """#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
"""

config_init = ""
config_settings = """import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework.authtoken",
    "channels", "django_celery_results",
    "finance", "users",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "mlm"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}

ASGI_APPLICATION = "config.asgi.application"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.TokenAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
"""

config_celery = """import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('mlm_platform')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
"""

config_asgi = """import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import path
from finance.consumers import WalletConsumer

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter([
            path("ws/wallets/", WalletConsumer.as_asgi()),
        ])
    ),
})
"""

config_urls = """from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken import views as drf_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-token-auth/', drf_views.obtain_auth_token),
    path('api/finance/', include('finance.urls')),
    path('api/users/', include('users.urls')),
]
"""

config_wsgi = """import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
"""

# Finance app files
finance_init = ""
finance_models = """from django.db import models
from django.conf import settings
from decimal import Decimal

WALLET_TYPES = [
    ("deposit","deposit"), ("staking","staking"),
    ("daily_profit","daily_profit"),
    ("total_profit","total_profit"),
    ("commission","commission"),
]

class Wallet(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallets")
    kind = models.CharField(max_length=32, choices=WALLET_TYPES)
    balance = models.DecimalField(max_digits=28, decimal_places=8, default=Decimal('0'))

    class Meta:
        unique_together = ("user", "kind")
"""

finance_serializers = """from rest_framework import serializers
from .models import Wallet

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ("id","kind","balance")
"""

finance_views = """from rest_framework import generics
from .models import Wallet
from .serializers import WalletSerializer

class WalletListView(generics.ListAPIView):
    serializer_class = WalletSerializer
    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)
"""

finance_services = """# Stub for wallet services (fill in with Decimal + atomic logic)
"""

finance_tasks = """from celery import shared_task

@shared_task
def example_task():
    return "celery works"
"""

finance_consumers = """from channels.generic.websocket import AsyncJsonWebsocketConsumer

class WalletConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send_json({"event": "connected"})
"""

finance_permissions = """from rest_framework import permissions

class IsAdminAnd2FA(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff
"""

finance_urls = """from django.urls import path
from .views import WalletListView

urlpatterns = [
    path('wallets/', WalletListView.as_view()),
]
"""

finance_tests_init = ""
finance_test_wallets = """from django.test import TestCase
from django.contrib.auth import get_user_model
from finance.models import Wallet

class WalletTest(TestCase):
    def test_wallet_creation(self):
        user = get_user_model().objects.create(username="u1")
        w = Wallet.objects.create(user=user, kind="deposit", balance=100)
        self.assertEqual(w.balance, 100)
"""

# Users app files
users_init = ""
users_models = """from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    referrer = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="referrals")
    totp_secret = models.CharField(max_length=32, blank=True, null=True)
"""

users_serializers = """from rest_framework import serializers
from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id","username","email")
"""

users_views = """from rest_framework import generics
from .models import User
from .serializers import UserSerializer

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
"""

users_urls = """from django.urls import path
from .views import UserListView

urlpatterns = [
    path('', UserListView.as_view()),
]
"""

# Frontend files
frontend_package = """{
  "name": "frontend",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "13.4.12",
    "react": "18.2.0",
    "react-dom": "18.2.0"
  }
}
"""

frontend_next_config = """module.exports = { reactStrictMode: true };"""

frontend_index = """export default function Home() {
  return <h1>Welcome to MLM Platform</h1>;
}
"""

frontend_dashboard = """import { useEffect, useState } from "react";

export default function Dashboard() {
  const [wallets, setWallets] = useState([]);

  useEffect(() => {
    fetch("/api/finance/wallets/", { credentials: "include" })
      .then(r => r.json())
      .then(setWallets);
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      <ul>
        {wallets.map(w => (
          <li key={w.id}>{w.kind}: {w.balance}</li>
        ))}
      </ul>
    </div>
  );
}
"""

frontend_wallets_panel = """export default function WalletsPanel({ wallets }) {
  return (
    <div>
      <h2>Wallets</h2>
      <ul>
        {wallets.map(w => (
          <li key={w.id}>{w.kind}: {w.balance}</li>
        ))}
      </ul>
    </div>
  );
}
"""

# File structure with contents
structure = {
    f"{PROJECT_NAME}/backend": {
        "manage.py": backend_manage,
        "config": {
            "__init__.py": config_init,
            "settings.py": config_settings,
            "celery.py": config_celery,
            "asgi.py": config_asgi,
            "urls.py": config_urls,
            "wsgi.py": config_wsgi,
        },
        "finance": {
            "__init__.py": finance_init,
            "models.py": finance_models,
            "serializers.py": finance_serializers,
            "views.py": finance_views,
            "services.py": finance_services,
            "tasks.py": finance_tasks,
            "consumers.py": finance_consumers,
            "permissions.py": finance_permissions,
            "urls.py": finance_urls,
            "tests": {
                "__init__.py": finance_tests_init,
                "test_wallets.py": finance_test_wallets,
            },
        },
        "users": {
            "__init__.py": users_init,
            "models.py": users_models,
            "serializers.py": users_serializers,
            "views.py": users_views,
            "urls.py": users_urls,
        },
    },
    f"{PROJECT_NAME}/frontend": {
        "package.json": frontend_package,
        "next.config.js": frontend_next_config,
        "pages": {
            "index.js": frontend_index,
            "dashboard.js": frontend_dashboard,
        },
        "components": {
            "WalletsPanel.js": frontend_wallets_panel,
        },
    },
        f"{PROJECT_NAME}/.vscode": {
        "extensions.json": """{
  "recommendations": [
    "ms-python.python",
    "batisteo.vscode-django",
    "ms-python.isort",
    "ms-python.black-formatter",
    "bibhasdn.django-html",
    "dsznajder.es7-react-js-snippets",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "eamodio.gitlens",
    "humao.rest-client",
    "mhutchie.git-graph",
    "ms-azuretools.vscode-docker"
  ]
}""",
        "settings.json": """{
  "editor.formatOnSave": true,
  "python.formatting.provider": "black",
  "python.analysis.typeCheckingMode": "basic",
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}"""
    },

}

def create_structure(base, tree):
    for name, content in tree.items():
        path = os.path.join(base, name)
        if isinstance(content, dict):
            os.makedirs(path, exist_ok=True)
            create_structure(path, content)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

if __name__ == "__main__":
    create_structure(".", structure)
    print(f"✅ Project '{PROJECT_NAME}' structure created successfully.")
# Compare this snippet from app.py:
# Search query
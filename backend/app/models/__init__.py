"""Импорт всех моделей регистрирует таблицы в общей metadata для Alembic."""

from app.models.balance import Balance as Balance
from app.models.event import Event as Event
from app.models.movement import Movement as Movement
from app.models.product import Product as Product
from app.models.seed_run import SeedRun as SeedRun
from app.models.store import Store as Store
from app.models.warehouse import Warehouse as Warehouse

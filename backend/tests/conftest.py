from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.ai_agent.models import AISettings
from apps.courses.models import Course, Group, TrialSlot
from apps.leads.models import Lead
from apps.organizations.models import Branch, Membership, Organization, WidgetSettings

_counter = itertools.count(1)


@dataclass
class OrgKit:
    org: Organization
    owner: User
    manager: User
    operator: User
    branch: Branch
    branch2: Branch
    course: Course
    course2: Course
    group: Group
    group2: Group
    slots: list = field(default_factory=list)
    widget: WidgetSettings | None = None

    def slot(self, *, days: int = 2, hour: int = 10, capacity: int = 4, group=None, status="open") -> TrialSlot:
        tz = timezone.get_default_timezone()
        import zoneinfo

        tz = zoneinfo.ZoneInfo(self.org.timezone)
        day = timezone.localtime(timezone.now(), tz).date() + timedelta(days=days)
        starts = datetime.combine(day, time(hour, 0), tzinfo=tz)
        return TrialSlot.objects.create(
            organization=self.org,
            group=group or self.group,
            starts_at=starts,
            ends_at=starts + timedelta(minutes=90),
            capacity=capacity,
            status=status,
        )

    def lead(self, **kwargs) -> Lead:
        n = next(_counter)
        defaults = {"organization": self.org, "source": "manual", "full_name": f"Test Mijoz {n}", "phone": f"+99800{n:07d}"}
        defaults.update(kwargs)
        return Lead.objects.create(**defaults)


def make_org(name: str = "Alpha Markaz", slug: str | None = None) -> OrgKit:
    n = next(_counter)
    slug = slug or f"org-{n}"
    org = Organization.objects.create(name=name, slug=slug, timezone="Asia/Tashkent")
    owner = User.objects.create_user(f"owner{n}@example.test", "Secret123!x", full_name=f"Owner {n}")
    manager = User.objects.create_user(f"manager{n}@example.test", "Secret123!x", full_name=f"Manager {n}")
    operator = User.objects.create_user(f"operator{n}@example.test", "Secret123!x", full_name=f"Operator {n}")
    Membership.objects.create(user=owner, organization=org, role="owner")
    Membership.objects.create(user=manager, organization=org, role="manager")
    Membership.objects.create(user=operator, organization=org, role="operator")
    branch = Branch.objects.create(organization=org, name=f"Markaz {n}", address="Sintetik ko'cha 1")
    branch2 = Branch.objects.create(organization=org, name=f"Shimoliy {n}", address="Sintetik ko'cha 2")
    course = Course.objects.create(organization=org, name="IELTS Intensive", price=Decimal("1200000"), keywords=["ielts"], description="IELTS tayyorlov")
    course2 = Course.objects.create(organization=org, name="Python asoslari", price=Decimal("900000"), keywords=["python"], description="Dasturlash")
    group = Group.objects.create(
        organization=org,
        course=course,
        branch=branch,
        name=f"IELTS-{n}",
        teacher_name="Maxfiy Ustoz",
        days=[0, 1, 2, 3, 4, 5, 6],
        start_time=time(10),
        end_time=time(11, 30),
    )
    group2 = Group.objects.create(
        organization=org,
        course=course2,
        branch=branch2,
        name=f"PY-{n}",
        teacher_name="Boshqa Ustoz",
        days=[0, 1, 2, 3, 4, 5, 6],
        start_time=time(18),
        end_time=time(20),
    )
    AISettings.objects.create(organization=org)
    widget = WidgetSettings.objects.create(organization=org, public_key=f"wk_test_{n}")
    return OrgKit(
        org=org,
        owner=owner,
        manager=manager,
        operator=operator,
        branch=branch,
        branch2=branch2,
        course=course,
        course2=course2,
        group=group,
        group2=group2,
        widget=widget,
    )


@pytest.fixture
def kit(db) -> OrgKit:
    return make_org("Alpha Markaz")


@pytest.fixture
def other_kit(db) -> OrgKit:
    return make_org("Beta Markaz")


@pytest.fixture
def client_for():
    def _client(user) -> APIClient:
        client = APIClient()
        client.force_login(user)
        return client

    return _client


@pytest.fixture
def anon_client() -> APIClient:
    return APIClient()

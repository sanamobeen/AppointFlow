# AppointFlow — Backend System Design

Status: living document. Update it as the system evolves.

## 1. Overview

AppointFlow is an appointment-booking platform. Businesses register through a
moderated onboarding flow (registration request → admin approval), then expose
their services and working hours so customers can book appointments with a
specific staff member at a specific time.

Stack: Django + Django REST Framework + SimpleJWT (email-based auth),
SQLite in development (Postgres planned for production), CORS enabled for a
separate frontend on `localhost:3000`.

## 2. Domain Modules

```
backend/           project config (settings, root urls)
accounts/          custom User (email login), signup/login/refresh/logout
businesses/        business categories, registration requests, businesses
services/          (planned) services a business offers: name, duration, price
staff/             (planned) staff members and their offered services, time off
bookings/          (planned) appointments — the core domain
notifications/     (planned) email/SMS on booking events
common/            (planned) shared permissions, pagination, utilities
```

## 3. Entity Relationships

```
User ──owns──▶ Business
BusinessCategory ──▶ Business
Business ──has many──▶ BusinessWorkingHours (one row per weekday)
Business ──has many──▶ Service          (name, duration, price, buffer)
StaffMember (User + Business + role) ──offers──▶ Service   (M2M)
StaffMember ──has many──▶ TimeOff
Customer (User) ──has many──▶ Booking ──▶ Service, StaffMember, Business
```

`BusinessRegistrationRequest` + `BusinessRegistrationHours` are **audit
records**, not live entities: on approval their data is *copied* into
`Business` + `BusinessWorkingHours` (+ owner account), never mutated.

## 4. Onboarding Flow

```
Anonymous visitor                Platform admin (is_staff)
      │                                  │
      │ POST /api/business-requests/     │ GET  /api/admin/business-requests/
      ▼                                  │ POST /api/admin/business-requests/{id}/approve/
 status=pending ────────────────▶ review ┤ POST /api/admin/business-requests/{id}/reject/
                                         ▼
                        approved: create Business + WorkingHours + owner User
                                  (find by owner_email, else create with
                                   unusable password → password reset)
                        rejected: store admin_notes, no side effects
```

Approval runs in a single transaction in `businesses/services.py` — the
service layer owns all business logic; views and serializers stay thin.

## 5. Booking System Design

**Availability is computed, never stored.**

```
available_slots(service, staff, date) =
    staff working hours for that weekday
  − existing non-cancelled bookings
  − staff time off
  − business closures/holidays
  split into (service.duration + buffer_time) slots
```

**Concurrency:** two customers targeting the same slot. Phase 1 uses
`select_for_update()` on the staff row inside a transaction; production
Postgres should add an overlap `ExclusionConstraint` as a hard guarantee.

**Booking state machine** (transitions enforced in the service layer):

```
pending → confirmed → completed
   ↓           ↓
cancelled   cancelled / no_show
```

Invalid transitions (e.g. cancelling after start time) raise validation errors.

## 6. API Surface

All endpoints are versioned under `/api/v1/` (legacy unversioned paths kept
working during migration).

### Auth (accounts)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/signup/` | public | create account, returns JWT pair |
| POST | `/api/v1/auth/login/` | public | returns JWT pair |
| POST | `/api/v1/auth/token/refresh/` | public | refresh access token |
| POST | `/api/v1/auth/logout/` | auth | blacklist refresh token |

### Onboarding (businesses)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/business-categories/` | public | active categories |
| POST | `/api/v1/business-requests/` | public | submit registration (multipart, nested working_hours) |
| GET | `/api/v1/admin/business-requests/` | staff | list all requests |
| POST | `/api/v1/admin/business-requests/{id}/approve/` | staff | approve → create Business |
| POST | `/api/v1/admin/business-requests/{id}/reject/` | staff | reject with `admin_notes` |

### Planned
| Method | Path | Auth |
|---|---|---|
| GET | `/api/v1/businesses/` | public (approved, filterable by category/city) |
| GET | `/api/v1/businesses/{slug}/services/` | public |
| GET | `/api/v1/businesses/{slug}/availability/?service=&staff=&date=` | public |
| POST / GET | `/api/v1/bookings/` | customer (own bookings) |
| GET / PATCH | `/api/v1/business/{slug}/bookings/` | business owner |

## 7. Permission Matrix

| Role | Capabilities |
|---|---|
| Anonymous | browse businesses/categories, signup/login, submit registration request |
| Customer | create/view/cancel own bookings |
| Business owner | manage own business, services, staff, incoming bookings |
| Platform admin (`is_staff`) | approve/reject registration requests |

Ownership checks live in DRF permission classes / queryset filtering
(`queryset.filter(owner=request.user)`), never in view bodies.

## 8. Cross-Cutting Conventions

- **Service layer**: business logic in `<app>/services.py`; views/serializers
  orchestrate only.
- **Config from environment**: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`,
  `CORS_ALLOWED_ORIGINS` read via `os.environ` (no committed secrets).
- **Serializers**: separate input vs response serializers for write endpoints
  (pattern already used in `businesses`).
- **Validation**: DB-level constraints (check/unique) for invariants that must
  never be violated, serializer-level for user-facing messages.
- **Testing**: every service function and public endpoint gets tests;
  availability calculation and booking conflicts are the highest-priority
  test surface.
- **Docs**: `drf-spectacular` OpenAPI schema once endpoints stabilize.

## 9. Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Env-based settings, admin approval endpoints, `Business` model promotion | in progress |
| 2 | `services` + `staff` apps, availability endpoint | planned |
| 3 | Booking creation with conflict handling, customer/owner booking views | planned |
| 4 | Notifications + reminders (Celery/Redis), Postgres migration | planned |
| 5 | Payments, reviews/ratings | ideas |

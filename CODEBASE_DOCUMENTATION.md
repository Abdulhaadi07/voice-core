# Voice Core - Codebase Documentation

## Project Overview

Voice Core is a Django-based multi-tenant voice communication platform that integrates with Wazo (an open-source VoIP platform) and AWS Cognito for authentication. The system manages users, tenants, SIP extensions, and voicemail services in a multi-tenant architecture.

**Technology Stack:**
- Django 4.x with Django REST Framework
- PostgreSQL (via DATABASE_URL)
- Celery for async tasks
- AWS Cognito for authentication
- Wazo API for VoIP services
- Docker for containerization

## Project Structure

```
voice_core/
├── config/                     # Django configuration
│   ├── settings/              # Environment-specific settings
│   ├── api_router.py          # API URL routing
│   ├── celery_app.py          # Celery configuration
│   ├── urls.py                # Main URL configuration
│   └── wsgi.py                # WSGI application
├── voice_core/                # Main application package
│   ├── custom_error_exception.py  # Custom API exceptions
│   ├── conftest.py            # Pytest configuration
│   ├── services/              # Business logic services
│   ├── tenant/                # Tenant management app
│   ├── users/                 # User management app
│   ├── utils/                 # Utility functions
│   └── templates/             # Django templates
├── tests/                     # Test files
├── requirements/              # Python dependencies
├── locale/                    # Internationalization
├── docs/                      # Documentation
├── compose/                   # Docker compose files
└── .envs/                     # Environment variables
```

## Core Applications

### 1. Tenant App (`voice_core/tenant/`)

**Purpose:** Manages multi-tenant architecture, allowing multiple organizations to use the platform independently.

#### Models

**`Tenant`** (`models.py`)
- **Purpose:** Represents an organization/company using the platform
- **Key Fields:**
  - `name`: Unique tenant name
  - `domain`: Optional domain for tenant
  - `max_users`: Maximum allowed users
  - `status`: Active/Inactive status
  - `wazo_tenant_uuid`: UUID for Wazo integration
  - `contexts`: JSON field for tenant-specific configuration
- **Relationships:** One-to-many with Users

#### API Views (`api/views/`)

**`TenantViewSet`** (`tenant_views.py`)
- CRUD operations for tenant management
- Tenant creation with Wazo integration
- Status management (activate/deactivate)

**`ExtensionViewSet`** (`extension_views.py`)
- **`available()`**: Lists available SIP extensions for a tenant
- **`assign()`**: Assigns SIP extension to a user
- Integrates with Wazo API for extension provisioning

**`VoicemailViewSet`** (`voicemail_views.py`)
- **`get_voicemail()`**: Retrieves voicemail configuration
- **`set_voicemail_configure()`**: Configures voicemail for user
- **`get_all_voicemail()`**: Gets all voicemail messages
- **`get_voicemail_by_folder()`**: Gets messages by folder
- **`set_message_status()`**: Updates message status
- **`get_message_recordings()`**: Streams voicemail recordings

### 2. Users App (`voice_core/users/`)

**Purpose:** Manages user authentication, profiles, and VoIP service assignments.

#### Models

**`User`** (`models.py`)
- **Purpose:** Custom user model extending Django's AbstractUser
- **Key Fields:**
  - `tenant`: Foreign key to Tenant (multi-tenancy)
  - `name`: User's display name
  - `email`: Unique email (USERNAME_FIELD)
  - `cognito_sub`: AWS Cognito user identifier
  - `wazo_user_id`: UUID for Wazo user
  - `wazo_username`: Username in Wazo system
  - `wazo_provisioned_at`: Timestamp of Wazo provisioning
  - `tenant_role`: Admin/Supervisor/Agent roles
  - `status`: Active/Inactive status
- **Manager:** Custom UserManager for email-based authentication

**`UserConfig`** (`models.py`)
- **Purpose:** User-specific configuration settings
- **Fields:**
  - `user`: OneToOne relationship with User
  - `voicemail_enabled`: Boolean flag
  - `extension_enabled`: Boolean flag

**`EncryptedCharField`** (`models.py`)
- **Purpose:** Custom field that encrypts data before saving to database
- **Methods:**
  - `get_prep_value()`: Encrypts value before DB save
  - `from_db_value()`: Decrypts value when reading from DB
- **Security:** Uses Fernet encryption with SIP_ENCRYPTION_KEY

**`ExtensionAssignment`** (`models.py`)
- **Purpose:** Links users to SIP extensions
- **Key Fields:**
  - `extension`: Extension number
  - `sip_username`: Encrypted SIP username
  - `sip_password`: Encrypted SIP password
  - `user`: Foreign key to User
  - `wazo_line_id`: Wazo line identifier
  - `context_name`: SIP context name

**`VoicemailAssignment`** (`models.py`)
- **Purpose:** Links users to voicemail boxes
- **Fields:**
  - `user`: Foreign key to User
  - `voicemail_id`: Wazo voicemail ID
  - `voicemail_pin`: Numeric PIN for access

#### API Views (`api/views/`)

**`UserViewSet`** (`user_views.py`)
- Standard CRUD operations for users
- User profile management
- Authentication integration

**`TenantUserViewSet`** (`tenant_user_views.py`)
- Tenant-scoped user operations
- User creation within specific tenants
- Role-based access control

#### Authentication (`signin/`, `registration/`)

**Registration Flow:**
1. User registers via API
2. AWS Cognito user created
3. Local User record created with cognito_sub
4. Email verification (if enabled)
5. Wazo user provisioning (async)

**Sign-in Flow:**
1. Cognito authentication
2. JWT token validation
3. Local user lookup by cognito_sub
4. Session establishment

#### Async Tasks (`tasks.py`)

**`send_email_task`**
- **Purpose:** Sends emails asynchronously via Celery
- **Features:**
  - Retry logic with exponential backoff
  - SMTP authentication error handling
  - HTML and plain text support
  - CC/BCC support

**`get_users_count`**
- **Purpose:** Demo task for Celery functionality
- **Returns:** Total user count

### 3. Services (`voice_core/services/`)

**Purpose:** Business logic and external service integrations.

#### Wazo Helpers (`wazo_helpers/`)

**`wazo_user.py`**
- **`create_wazo_user()`**: Creates user in Wazo system
  - Generates random password
  - Creates user with authentication
  - Returns wazo_user_id and username
- **`generate_valid_password()`**: Creates secure passwords

**`wazo_tenant.py`**
- Tenant management in Wazo
- Context creation and configuration

**`wazo_extensions.py`**
- SIP extension management
- Line provisioning
- Extension assignment

**`wazo_voicemail.py`**
- Voicemail box creation
- Configuration management
- Message retrieval

**`wazo_admin_token.py`**
- Authentication token management
- Token refresh logic

**`wazo_context.py`**
- SIP context management
- Dialplan configuration

**`wazo_sip_template.py`**
- SIP endpoint templates
- Configuration templates

#### Extensions (`extensions/`)
- Extension-specific business logic
- SIP configuration management

#### Voicemail (`voicemail/`)
- Voicemail service integration
- Message processing logic

### 4. Configuration (`config/`)

#### Settings (`settings/`)

**`base.py`**
- Core Django settings
- Database configuration
- Security settings
- External service URLs (Wazo, AWS)

**`local.py`**
- Development environment settings
- Debug configurations
- Local service endpoints

**`production.py`**
- Production environment settings
- Security hardening
- Performance optimizations

**`test.py`**
- Test environment settings
- Test database configuration
- Mock service configurations

#### API Router (`api_router.py`)

**URL Patterns:**
- `/api/users/` - User management
- `/api/tenants/` - Tenant management
- `/api/tenants/{id}/users/` - Tenant-scoped user operations
- `/api/tenants/{id}/extensions/` - Extension management
- `/api/tenants/{id}/users/{id}/voicemail/` - Voicemail operations

#### Celery Configuration (`celery_app.py`)
- Celery app initialization
- Task discovery
- Broker configuration

### 5. Utilities (`voice_core/utils/`)

**`mail.py`**
- Email utility functions
- Template rendering
- SMTP configuration helpers

### 6. Custom Exceptions (`custom_error_exception.py`)

**Custom Exception Classes:**
- `BadGateway` (502)
- `ServiceUnavailable` (503)
- `GatewayTimeout` (504)
- `NotImplementedAPI` (501)
- `Conflict` (409)

**Helper Functions:**
- **`raise_custom_drf_exception()`**: Maps HTTP status codes to DRF exceptions
- **`extract_error_message()`**: Extracts readable error messages from complex exception objects

## Cross-File Dependencies and Workflows

### 1. User Registration Workflow

```
Registration Request → UserViewSet → User.objects.create() → 
Cognito Integration → Wazo User Creation (async) → 
Email Notification (Celery) → User Provisioned
```

**Files Involved:**
- `users/api/views/user_views.py` - API endpoint
- `users/models.py` - User model
- `users/tasks.py` - Email task
- `services/wazo_helpers/wazo_user.py` - Wazo integration

### 2. Extension Assignment Workflow

```
Extension Request → ExtensionViewSet.assign() → 
Wazo Extension Creation → ExtensionAssignment.create() → 
SIP Credentials Encryption → User Notification
```

**Files Involved:**
- `tenant/api/views/extension_views.py` - API endpoint
- `services/wazo_helpers/wazo_extensions.py` - Wazo integration
- `users/models.py` - ExtensionAssignment model
- `users/models.py` - EncryptedCharField

### 3. Voicemail Configuration Workflow

```
Voicemail Request → VoicemailViewSet → 
Wazo Voicemail Creation → VoicemailAssignment.create() → 
UserConfig Update → Configuration Response
```

**Files Involved:**
- `tenant/api/views/voicemail_views.py` - API endpoint
- `services/wazo_helpers/wazo_voicemail.py` - Wazo integration
- `users/models.py` - VoicemailAssignment, UserConfig

### 4. Multi-Tenant Data Isolation

```
API Request → Authentication → Tenant Resolution → 
Tenant-Scoped Queries → Data Filtering → Response
```

**Implementation:**
- All models have tenant relationships
- API views filter by tenant context
- Wazo operations use tenant-specific UUIDs

### 5. Error Handling Flow

```
Service Error → Custom Exception → 
Error Message Extraction → 
HTTP Status Code Mapping → 
Standardized API Response
```

**Files Involved:**
- `custom_error_exception.py` - Exception definitions
- All API views - Error handling
- Service helpers - Error propagation

## Security Features

### 1. Data Encryption
- **SIP Credentials**: Encrypted using Fernet symmetric encryption
- **Encryption Key**: Stored in environment variable `SIP_ENCRYPTION_KEY`
- **Fields**: `sip_username`, `sip_password` in ExtensionAssignment

### 2. Multi-Tenant Isolation
- **Database Level**: All models linked to tenant
- **API Level**: Tenant-scoped endpoints
- **Wazo Level**: Tenant-specific UUIDs

### 3. Authentication
- **AWS Cognito**: External authentication provider
- **JWT Tokens**: Stateless authentication
- **Role-Based Access**: Admin/Supervisor/Agent roles

### 4. Input Validation
- **DRF Serializers**: Request validation
- **Model Validation**: Database constraints
- **Custom Validators**: Business rule validation

## External Integrations

### 1. AWS Cognito
- **Purpose**: User authentication and management
- **Configuration**: Via environment variables
- **Integration Points**: User registration, login, token validation

### 2. Wazo API
- **Purpose**: VoIP service provisioning
- **Endpoints**: User, tenant, extension, voicemail management
- **Authentication**: Admin token-based
- **Configuration**: WAZO_API_URL, admin credentials

### 3. Email Services
- **Purpose**: User notifications and communications
- **Backend**: Configurable SMTP
- **Async Processing**: Via Celery tasks
- **Templates**: Django template system

### 4. Celery/Redis
- **Purpose**: Async task processing
- **Tasks**: Email sending, user provisioning
- **Configuration**: Via Django settings
- **Monitoring**: Celery beat for periodic tasks

## Development and Testing

### 1. Testing Framework
- **Framework**: pytest with Django plugin
- **Configuration**: `pytest.ini`, `conftest.py`
- **Coverage**: django-coverage-plugin
- **Commands**: `pytest`, `coverage run -m pytest`

### 2. Code Quality
- **Linting**: Ruff for Python linting
- **Type Checking**: mypy with Django stubs
- **Formatting**: Ruff formatting
- **Pre-commit**: Automated quality checks

### 3. Docker Configuration
- **Development**: `docker-compose.local.yml`
- **Production**: `docker-compose.production.yml`
- **Testing**: `docker-compose.dev-testing.yml`
- **Documentation**: `docker-compose.docs.yml`

### 4. Environment Management
- **Local**: `.envs/.local/`
- **Production**: Environment-specific variables
- **Required Variables**: Database, AWS, Wazo, Email credentials

## API Documentation

### Authentication Endpoints
- `POST /auth/register/` - User registration
- `POST /auth/login/` - User login
- `POST /auth/logout/` - User logout

### User Management
- `GET /api/users/` - List users
- `POST /api/users/` - Create user
- `GET /api/users/{id}/` - Get user details
- `PATCH /api/users/{id}/` - Update user

### Tenant Management
- `GET /api/tenants/` - List tenants
- `POST /api/tenants/` - Create tenant
- `GET /api/tenants/{id}/` - Get tenant details

### Tenant-Scoped Operations
- `GET /api/tenants/{id}/users/` - List tenant users
- `POST /api/tenants/{id}/users/` - Create tenant user
- `GET /api/tenants/{id}/extensions/available/` - Available extensions
- `POST /api/tenants/{id}/users/{user_id}/assign/` - Assign extension

### Voicemail Operations
- `GET /api/tenants/{id}/users/{user_id}/voicemail/config` - Get voicemail config
- `POST /api/tenants/{id}/users/{user_id}/voicemail/config` - Configure voicemail
- `GET /api/tenants/{id}/users/{user_id}/voicemail/messages` - Get messages
- `PUT /api/tenants/{id}/users/{user_id}/voicemail/messages/{msg_id}/status/` - Update message status

## Deployment Considerations

### 1. Environment Variables
- Database connection string
- AWS credentials and region
- Cognito configuration
- Wazo API credentials
- Email service configuration
- Encryption keys

### 2. Database Migrations
- Run `python manage.py migrate` for schema updates
- Backup database before production migrations
- Test migrations in staging environment

### 3. Static Files
- Collect static files: `python manage.py collectstatic`
- Configure web server for static file serving
- CDN integration for production

### 4. Monitoring and Logging
- Configure logging levels per environment
- Monitor Celery task queues
- Track API response times and errors
- Monitor external service integrations

This documentation provides a comprehensive guide to understanding the Voice Core codebase, its architecture, and the workflows that connect different components of the system.
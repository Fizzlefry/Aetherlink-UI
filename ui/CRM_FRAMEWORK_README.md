# AetherLink Unified CRM Framework

This directory contains the unified CRM interface framework for all AetherLink verticals (PeakPro, RoofWonder, PolicyPal, Clientellme, ApexFlow).

## Architecture

### Core Components (`crm-lib/`)
- **CrmShell**: Standard layout with top bar, collapsible nav, main content, and right rail
- **PipelineView**: Kanban-style deal/job tracking with stages
- **RecordView**: Two-column detailed record view (details + messages/docs)
- **AutomationsView**: Rule-based automation builder (When → Then)

### Vertical Implementations (`verticals/`)
Each vertical has its own CRM app that:
- Uses the shared `crm-lib` components
- Fetches data from `/ui/bundle` endpoint
- Displays vertical-specific mock data
- Integrates AetherLink status in the right rail

## Key Features

### Three Main Views
1. **Pipeline View**: Visual deal progression through stages
2. **Record View**: Comprehensive record details with activity feed
3. **Automations View**: Configurable business rules and triggers

### AetherLink Integration
- Real-time status from `/ui/bundle`
- Service health indicators
- Active alerts display
- Federation status awareness
- Policy and learning insights

### Customization Options
- User-defined layouts and visible panels
- Role-based field visibility
- Switchable compact/comfortable/Kanban modes
- Theming support (light/dark mode ready)

## Usage

### For New Verticals
1. Create new file in `verticals/` (e.g., `RoofWonderCRM.tsx`)
2. Import shared components from `../crm-lib`
3. Implement vertical-specific data and logic
4. Use `CrmShell` as the root component

### Data Flow
```
CRM App → /ui/bundle → Command Center → Aggregated Data
```

### Actions
- POST `/alerts/ack` for alert acknowledgment
- POST `/federation/policy/apply` for policy application
- All other actions go through existing backend APIs

## Development Guidelines

### Always use `/ui/bundle`
- Fetch all dashboard data from single endpoint
- Do not call multiple endpoints individually
- Extend bundle shape in Command Center if needed

### Consistent UI Patterns
- Use Tailwind CSS classes
- Follow the CrmShell layout structure
- Include AetherLink status awareness
- Support responsive design

### Backend Integration
- Connect to existing endpoints for business logic
- Use federation auth where required
- Handle errors gracefully with fallbacks

## Running the Framework

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:5173
```

## Vertical Status

- ✅ **PeakPro CRM**: Roofing services pipeline
- ✅ **PolicyPal CRM**: Insurance policy management
- 🔄 **RoofWonder CRM**: To be implemented
- 🔄 **Clientellme CRM**: To be implemented
- 🔄 **ApexFlow CRM**: To be implemented

## Future Enhancements

- AI-assisted content generation
- Advanced customization dashboard
- Multi-tenant support
- Real-time collaboration features
- Mobile-responsive optimizations

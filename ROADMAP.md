# Roadmap
This is the Roadmap for the Bot / Project

## Version 1.0 ✅ COMPLETED
- [x] Forwarding logs
- [x] QoL, cleaning code & bug fixes

## Version 2.0 ✅ COMPLETED
### Structure Change
- [x] From JSON to SQLite Database (upgraded from TinyDB plan)
    - [x] For the server_config.json
    - [x] Complete database handler class implementation
    - [x] Guild configuration management
    - [x] Log settings per guild

### Self Logging ✅ COMPLETED
Logging -
- [x] Profile Changes (Name, Profile Picture, Nickname, Roles, etc.)
- [x] Role Changes (Role added to user, Role removed from user, Role created, Role deleted, etc.)
- [x] Message edit/deleted/bulk delete
- [x] Member join/leave/ban/unban events
- [x] Reaction add/remove/clear events
- [x] Channel create/delete/update events
- [x] Voice channel join/leave/move events
- [x] Emoji and sticker events
- [x] Webhook and invite events

### Additional Features Completed
- [x] Comprehensive slash command system
- [x] Database migration and setup commands
- [x] Enhanced error handling and logging
- [x] Configurable log settings per event type
- [x] Self-logging toggle functionality
- [x] Maintenance mode support
- [x] Cross-platform update system with backup creation
- [x] Automated log cleanup with retention policies
- [x] Multi-server forwarding support

## Version 3.0 🚧 IN PLANNING
### Integrated Features
- [ ] Ticket System
- [ ] Web Dashboard
- [ ] Advanced filtering options for logs
- [ ] Role-based access control for commands
- [ ] Scheduled maintenance windows
- [ ] Export logs functionality
- [ ] Automatic checks for updates for self hosted instances

### Performance & Scalability
- [ ] Database optimization for large servers
- [ ] Caching layer implementation
- [ ] Rate limiting improvements
- [ ] Memory usage optimization

### User Experience
- [ ] Interactive setup wizard
- [ ] In-Discord configuration panels
- [ ] Real-time log previews
- [ ] Mobile-friendly web interface
# Fedresurs Pro Skill — Setup Guide

## Installation on VPS

```bash
# 1. Copy skill to VPS
rsync -avz ./fedresurs-pro-skill/ root@157.22.231.149:/mnt/skills/user/fedresurs-pro/

# 2. Verify
ssh root@157.22.231.149 "ls -la /mnt/skills/user/fedresurs-pro/"
```

---

## Setup in Claude Code

**Already works automatically!**

Claude Code reads `/mnt/skills/` by default when connected to VPS.

Verify:
```bash
# In Claude Code chat
"What skills do you have access to?"
```

Should respond: `fedresurs-pro` (and public skills like docx, pdf, pptx)

---

## Setup in Cursor (with Cline/Kilo Code Extensions)

### 1. Mount VPS via SSH

In Cursor:
1. Press `F1` → `Remote-SSH: Connect to Host`
2. Enter: `root@157.22.231.149`
3. Open folder: `/mnt/skills`

### 2. Configure Cline

Create `.clinerules` in workspace root:

```
Skills location: /mnt/skills/user/fedresurs-pro
Always read SKILL.md before starting tasks.
Check references/ for detailed documentation:
- ORCHESTRATOR.md: Search cycle, limit protection
- DATABASE.md: Schema, queries, datasets
- API.md: Parser API, Checko, Rosreestr
- DEBUGGING.md: Troubleshooting checklists
- DEPLOYMENT.md: Docker, nginx, infrastructure

Use scripts/ for manual testing:
- scripts/check-limits.sh: Check API quotas
- scripts/check-db.sh: Database health
- scripts/debug-search.py: Manual search test
```

### 3. Configure Kilo Code

Add to Kilo Code settings (via extension settings):

**System Prompt:**
```
You have access to project skills in /mnt/skills/user/fedresurs-pro/.

Read SKILL.md for architecture overview before any task.
Check references/ for detailed documentation when needed.
Use scripts/ for manual testing and diagnostics.

Key reference files:
- ORCHESTRATOR.md: Search cycle and API limit protection
- DATABASE.md: Database schema and queries
- API.md: External API documentation
- DEBUGGING.md: Common issues and fixes
- DEPLOYMENT.md: Infrastructure and deployment
```

### 4. Configure Cursor AI

Create `.cursorrules` in workspace root:

```
Project: Fedresurs Pro
Skills: /mnt/skills/user/fedresurs-pro

Read SKILL.md for architecture overview.
Use references/ for detailed documentation.
Follow debugging checklists in references/DEBUGGING.md.

Database: fedr-db-1 container, fedresurs_db
API: http://157.22.231.149:8000
Frontend: http://157.22.231.149
```

---

## Skill Structure

```
fedresurs-pro/
├── SKILL.md                    # Main overview (read first)
│
├── references/                 # Detailed docs
│   ├── ORCHESTRATOR.md         # Search cycle, limits
│   ├── DATABASE.md             # Schema, queries
│   ├── API.md                  # External APIs
│   ├── DEBUGGING.md            # Troubleshooting
│   └── DEPLOYMENT.md           # Infrastructure
│
└── scripts/                    # Utility scripts
    ├── check-limits.sh         # Check API quotas
    ├── check-db.sh             # Database health
    └── debug-search.py         # Manual search test
```

---

## Usage

### In Any Agent

**Simple task:**
```
"Check orchestrator status"
```

Agent will:
1. See `fedresurs-pro` in skill list
2. Read `SKILL.md` (brief overview)
3. Run: `docker logs fedr-app-1 | grep ...`

**Complex task:**
```
"Debug why orchestrator is in infinite loop"
```

Agent will:
1. Read `SKILL.md`
2. Read `references/DEBUGGING.md`
3. Check `references/ORCHESTRATOR.md`
4. Run diagnostic commands
5. Apply fixes

**Research task:**
```
"How does the enrichment pipeline work?"
```

Agent will:
1. Read `SKILL.md`
2. Read `references/API.md` (Checko, Rosreestr)
3. Read `references/DATABASE.md` (data flow)
4. Explain with code references

---

## Benefits

### Token Efficiency

**Without skill:**
- Agent reads full CLAUDE.md (50K tokens) every time
- Even for simple "check logs" tasks

**With skill:**
- Simple task → reads SKILL.md (2K tokens)
- Medium task → + references/DEBUGGING.md (5K tokens)
- Complex task → + multiple references (15K tokens)

**Savings**: 3-10x fewer tokens on most tasks

### Agent Switching

All agents read the same files:
- Claude Code ✓
- Cline ✓
- Kilo Code + DeepSeek ✓
- Cursor AI ✓

Switch between them without losing context.

### Version Control

```bash
cd /mnt/skills/user/fedresurs-pro
git init
git add .
git commit -m "Initial skill version"
```

Rollback if skill breaks:
```bash
git log --oneline
git reset --hard <commit>
```

---

## Maintenance

### Update Skill

```bash
# Edit on local machine
vim fedresurs-pro-skill/references/ORCHESTRATOR.md

# Sync to VPS
rsync -avz ./fedresurs-pro-skill/ root@157.22.231.149:/mnt/skills/user/fedresurs-pro/
```

All agents see update immediately!

### Check Skill Status

```bash
# On VPS
cat /mnt/skills/user/fedresurs-pro/SKILL.md | head -20

# Check references
ls -lh /mnt/skills/user/fedresurs-pro/references/
```

---

## Validation

Use skills-ref tool (optional):

```bash
# Install
pip install skills-ref

# Validate
skills-ref validate /mnt/skills/user/fedresurs-pro
```

Checks:
- SKILL.md frontmatter valid?
- Name matches directory?
- All required fields present?

---

## Troubleshooting

### Agent doesn't see skill

**Check path:**
```bash
ssh root@157.22.231.149 "ls /mnt/skills/user/fedresurs-pro/SKILL.md"
```

**Restart agent** (especially Cursor extensions)

### Agent reads wrong file

**Check SKILL.md references:**
```bash
grep -r "references/" /mnt/skills/user/fedresurs-pro/SKILL.md
```

Make sure paths are relative, not absolute.

### Skill too large

**Check file sizes:**
```bash
find /mnt/skills/user/fedresurs-pro -type f -exec du -h {} + | sort -h
```

Recommendation:
- SKILL.md: < 5K tokens (~20KB)
- Each reference: < 10K tokens (~40KB)

If larger, split into more files.

---

## Next Steps

1. **Deploy skill** to VPS
2. **Test** with simple query in each agent
3. **Update** SKILL.md as project evolves
4. **Monitor** token usage (should drop 3-10x)

Enjoy unified knowledge base across all agents! 🎉

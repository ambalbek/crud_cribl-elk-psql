# Git History Cleanup

## Problem

`untracked_apmids/apmids-blob.tar.part_a{a,b}` (~57 MB) is committed to the
repository.  Binary archives inflate clone size and slow CI.

## Removal with git filter-repo

> **Do not run these commands without coordinating with the team.**  This
> rewrites history and requires every contributor to re-clone or rebase.

```bash
# 1. Install git-filter-repo (pip, brew, or apt)
pip install git-filter-repo

# 2. Back up the repo
cp -r .git .git-backup

# 3. Remove the blobs from all commits
git filter-repo --path untracked_apmids/ --invert-paths

# 4. Force-push to the remote (coordinate first!)
git push origin --force --all
git push origin --force --tags
```

After the rewrite every existing clone is stale.  Contributors must either
fresh-clone or run:

```bash
git fetch origin
git reset --hard origin/main
```

## Credential Rotation Checklist

The `.env` file was committed with values in it.  Even after `filter-repo`
removes the file from history, any secrets that were ever pushed should be
considered compromised.

- [ ] Rotate `CRIBL_TOKEN`
- [ ] Rotate `ECE_ES_TOKEN` (nonprod and prod)
- [ ] Rotate `ECE_ES_PASSWORD` (nonprod and prod)
- [ ] Rotate `ECE_KIBANA_TOKEN`
- [ ] Rotate `ECE_KIBANA_PASSWORD`
- [ ] Rotate any Azure Storage connection strings present in blob dest templates
- [ ] Verify `.env` is in `.gitignore` (currently only in `.claudeignore`)
- [ ] Audit `config.json` for any embedded credentials

## Prevention

Add to `.gitignore`:

```
.env
.env.*
!.env.example
untracked_apmids/
*.tar
*.tar.*
```

---
name: work-in-git-tree
description: Define rules how AI agent must work in a separate git worktree to avoid conflicts with user's parallel work
whenToUse: work on any tasks in a git repository
tags:
  - workflow
  - git
---
# Goal
- Eliminate conflicts when the user and the AI agent work on the same repository in parallel
- Isolate the agent's changes in a separate workspace until they are merged via a pull request

# Core Principle
- The AI agent performs all work in a separate git worktree linked to its own branch
- The user continues working in the main repository without the risk of conflicts caused by the agent's unfinished changes

# How to work
1. Before creating the worktree, push the base branch to the remote server to synchronize the current repository with the server
   ```bash
   git push origin {base-branch}
   ```

2. Create a new git worktree and a task branch
   - Branch from `develop` unless the user specifies a different base branch
   - The worktree and branch name should reflect the task
   
   ```bash
   git worktree add ./.ai-worktree/{task-name} -b {task-name} {base-branch}
   ```
   
   Example:
   ```bash
   git worktree add ./.ai-worktree/add-auth-service -b add-auth-service develop
   ```

3. Switch to the worktree and work only inside it
   ```bash
   cd ./.ai-worktree/{task-name}
   ```

4. Commit your changes to the worktree branch as you progress
   ```bash
   git add .
   git commit -m "feat: ..."
   ```

5. When the work is done, create a pull request from the worktree branch into the base branch (the one the task branch was created from)
   ```bash
   # Example using GitHub CLI
   gh pr create --base develop --head {task-name} --title "..." --body "..."
   ```

6. After the PR is merged, the worktree can be removed
   ```bash
   cd /path/to/main/repo
   git worktree remove ./.ai-worktree/{task-name}
   git branch -d {task-name}
   ```

# Rule
## MUST
- The AI agent modifies files only inside its own worktree (`./.ai-worktree/{task-name}`).
- The AI agent commits only inside its own worktree, on the dedicated task branch.
- At the end of the work, a pull request must be created into the base branch the task branch was created from.
## SHOULD
- The branch and worktree name should be unique and descriptive, so they are not confused with the user's branches.
- The agent should verify that the base branch exists and is up to date before creating the worktree.

## MAY
- Multiple worktrees may be created if several branches need to be available at once (for example, for parallel tasks or experiments).
## MUST NOT
- The agent must not modify files in the main repository or in another user's worktree.

# Anti-patterns
- **Modifying files in the main repository instead of the worktree**
  - The user may be editing the same files at the same time. This leads to merge conflicts, lost changes, and an inability to create a clean pull request.
  
- **Relying on data from the main repository or another worktree**
  - The user can change the state of the main repository at any time. The agent may make decisions based on stale data, which causes implementation errors.
  
- **Committing directly to the base branch (for example, `develop`) from the worktree**
  - This bypasses code review and may break the shared branch if the changes have not been validated.
  
- **Creating a worktree without a dedicated branch**
  - Without a separate branch, all changes end up on the base branch, defeating the purpose of isolation and increasing the risk of conflicts.

# Check list
- [ ] `./.ai-worktree` is added to the main repository's `.gitignore`
- [ ] A worktree is created at `./.ai-worktree/{task-name}`
- [ ] A dedicated `{task-name}` branch is created from the base branch (default is `develop`)
- [ ] All file changes are made only inside the worktree
- [ ] All commits are made only on the worktree branch
- [ ] A pull request is created into the base branch at the end

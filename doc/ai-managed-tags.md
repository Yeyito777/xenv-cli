# xenv and dwm AI-managed tags

This document explains how `xenv` integrates with the AI-managed tag system in the host dwm.

## Why this exists

`xenv` launches a nested Xephyr window on the host X session. Without special handling, that Xephyr window appears on the currently focused host tag and interrupts the user's work.

To avoid that, `xenv` marks its Xephyr launch as AI-managed so the host dwm can place it on a dedicated tag.

## What xenv does

When `xenv start <name>` launches Xephyr, it exports:

- `DWM_AI_TAG=1`
- `DWM_AI_TOKEN=xenv:<name>`
- `DWM_AI_LABEL=xenv: <name>`
- `DWM_AI_POLICY=autodelete-pristine`

It also keeps the older Xephyr markers as a compatibility fallback:

- `-name exo-xenv-<name>`
- `-title xenv: <name>`

So a modern host dwm can use the generic `DWM_AI_*` contract, while older patched builds can still recognize the window by WM class/title.

## Expected behavior on the host dwm

If the host dwm supports AI-managed tags, the Xephyr host window should:

- land on a new far-right tag
- not steal focus on initial map
- show the AI-specific tag color while pristine
- auto-delete its tag when stopped, as long as the tag stayed pristine

If another unrelated window is added to that same tag, the tag is demoted to a normal tag and no longer auto-deletes.

## Token choice

`xenv` uses one token per named instance:

- instance `demo` -> token `xenv:demo`
- instance `agent-7` -> token `xenv:agent-7`

That means all windows belonging to one logical `xenv` instance can share the same AI-managed tag.

## Example

Starting:

```sh
xenv start demo
```

Internally launches Xephyr with environment similar to:

```sh
DWM_AI_TAG=1
DWM_AI_TOKEN=xenv:demo
DWM_AI_LABEL="xenv: demo"
DWM_AI_POLICY=autodelete-pristine
Xephyr -name exo-xenv-demo -title "xenv: demo" ...
```

## Relationship to `dwm-ai-launch`

The host dwm repo also provides a generic helper:

```sh
dwm-ai-launch --token TOKEN [--label LABEL] -- command [args...]
```

`xenv` currently exports the environment variables directly instead of invoking that helper, but the contract is the same.

## Testing checklist

To verify integration:

1. start an xenv instance
2. confirm the current host focus does not change
3. confirm a new far-right tag appears
4. confirm the xenv window lives there
5. stop the xenv instance
6. confirm the tag disappears again

Optional contamination test:

1. start an xenv instance
2. switch to its tag
3. open another unrelated host window there
4. confirm the AI-colored state disappears
5. stop xenv
6. confirm the tag remains, because it was demoted to a normal tag

## Files of interest

- `src/lifecycle.py`
- `README.md`

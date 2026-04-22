# Agent Knowledge Hub

A marketplace where the SLAC community discovers, shares, and installs knowledge for their AI assistants — without needing to know how any of it works under the hood.

## Browse. Share. Install.

Your AI coding assistant is only as useful as the knowledge it has access to. Agent Knowledge Hub is the place to find capabilities built by your colleagues for problems you actually have — querying accelerator systems, diagnosing cluster issues, analysing scientific data.

See what the community rates highly, filter by topic, read a description, and decide in seconds whether it's worth trying.

Browse all community labels at [/labels](https://agent-knowledge-hub.slac.stanford.edu/labels), or click any label chip on a skill card to filter the catalog to that topic. On a skill's detail page, authenticated users can add free-form labels using an inline typeahead combobox.

Skills in private SLAC GitHub repos are fully supported. Skills that require SLAC GitHub access are shown with a **SLAC Members Only** badge so you know upfront — and a link explaining how to get access.

## Share what you've built

Have something useful to share? `/agent-knowledge-hub` walks you through the whole process:

```
/agent-knowledge-hub submit
```

It will guide you through creating a new GitHub repo (or adding to an existing one), structuring your skill, and registering it in the catalog — step by step, without leaving your assistant.

## Install without leaving your assistant

Ask your AI assistant what you need, in plain English, and it finds and installs the right knowledge for you — without leaving the conversation.

```
/agent-knowledge-hub I'm trying to figure out what's wrong with my Kubernetes deployment
/agent-knowledge-hub find me something for analysing NeXus files
```

No configuration. No manual file copying.

Register the SLAC marketplace once to get started:

```
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json
/plugin install agent-knowledge-hub
```

## Links

- Catalog: [agent-knowledge-hub.slac.stanford.edu](https://agent-knowledge-hub.slac.stanford.edu)
- Questions? Find us on SLAC Slack.

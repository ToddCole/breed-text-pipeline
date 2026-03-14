# Breed Text Pipeline

A lightweight editorial pipeline for generating structured dog breed profiles using 
LLMs.

The tool was built to speed up the creation and refinement of breed descriptions, 
temperament summaries, grooming notes and other structured editorial fields while 
maintaining a consistent tone of voice.

## What it does

The pipeline generates and refines text fields such as:

- Breed description
- Temperament summary
- Exercise requirements
- Grooming notes
- Training characteristics
- Signature lines
- SEO metadata

It uses a structured prompt system and field-specific constraints to keep output 
concise, breed-specific and editorially consistent.

## Why it exists

Large breed directories require hundreds of individual descriptions.  
Writing them manually is slow and inconsistent.

This pipeline allows an editor to:

- generate first drafts quickly
- rewrite existing text into a consistent tone
- tighten or expand sections
- maintain style rules across hundreds of entries

The goal is **editorial assistance**, not blind automation.

## Key ideas

- Field-specific prompts for better control
- Tone-of-voice enforcement
- Length constraints per field
- Breed trait context passed into prompts
- Multi-pass rewriting for quality

## Tech stack

- Python
- Anthropic API
- dotenv for key management

## Running locally

Clone the repo and install requirements:


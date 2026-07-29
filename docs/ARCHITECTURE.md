# Architecture

## 1. Portable contract

The portable layer contains the value types, validation, revisions, events, NBT projection, lifecycle service, and atomic reference adapter. It has no Bedrock ABI dependency and is built on Linux and Windows with warnings treated as errors.

## 2. Public Endstone placement boundary

Native placement and removal should use Endstone's public block-data APIs where possible. The sign block ID and typed state map are built before mutation. A placed block is then resolved to its exact `SignBlockActor` before text or editor operations continue.

## 3. Exact `SignBlockActor` bridge

Private sign behavior is isolated in `src/verified_bds_26_30_adapter.cpp`. That file does not exist in the source release. It is introduced only after exact-binary review.

The verified bridge is responsible for:

- full front/back capture;
- all text and style writes;
- wax and editor-lock state;
- native editor requests;
- player-edit interception before mutation;
- block-actor dirty marking and client updates;
- persistence and transaction rollback.

## 4. Binary identity

`inspectCurrentProcessExecutable()` hashes the running server executable. Activation compares its SHA-256 and byte size against the generated manifest. A version string alone is never accepted as binary identity.

## 5. Symbol manifest

Each platform manifest records exactly one official BDS package, one executable identity, 19 required behavior anchors, ABI review, hook proof, bridge proof, and stage-probe evidence. The activation tool generates the C++ header only when the verifier reports no missing requirements.

## 6. Registration barrier

The plugin constructs the guarded adapter first. It registers `endstone:sign:v2` only if `SignCapabilities::completeControl()` is true. Consumers therefore never receive an object whose methods quietly return placeholders.

## 7. Transaction model

The portable reference adapter applies operations to a private candidate state and publishes that state only on success. The native bridge must provide equivalent all-or-nothing behavior, including rollback of block replacement, block-actor state, editor locks, and client-visible updates.

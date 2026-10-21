# ADR

* [ADR-0000 Template](ADR-0000-template.md) - copy this to start a new ADR
* [ADR-0001 Every pass also runs alone as a pipeable filter](ADR-0001-passes-are-pipeable-filters.md) - stages compose as a shell pipeline
* [ADR-0002 FON is the protocol between stages](ADR-0002-fon-is-the-stage-protocol.md) - FON on stdin and stdout
* [ADR-0003 FON is an FPL subset that materialises native ABTs](ADR-0003-fon-is-an-fpl-subset.md) - ABTs inside, ASCII postfix FON outside
* [ADR-0004 Native ABTs within an address space, FON only across a boundary](ADR-0004-native-abts-fon-at-boundaries.md) - defonify >> stage >> fonify at a process boundary
* [ADR-0005 The boundary operation is fonify, its inverse defonify](ADR-0005-fonify-defonify.md) - the names at the wire
* [ADR-0006 One fpl executable with a subcommand per stage](ADR-0006-one-fpl-executable.md) - fpl source | fpl lex | ... | fpl render
* [ADR-0007 The CLI may use third-party libraries](ADR-0007-cli-libraries-welcome.md) - the standard library is no constraint; Click is in use
* [ADR-0008 FPL's object language is dependent call-by-push-value](ADR-0008-object-language-dependent-cbpv.md) - the core is dependent CBPV
* [ADR-0009 Keep information as long as possible; strip only in an optimising release build](ADR-0009-keep-information-strip-at-release.md) - debug by default, -O strips
* [ADR-0010 Staging is first-class: the compiler is an FPL library](ADR-0010-first-class-staging.md) - passes are values the language can call
* [ADR-0011 FPL aims to match or surpass Lisp in metaprogramming](ADR-0011-lisp-level-metaprogramming.md) - operatives through staging
* [ADR-0012 The pipeline is an inspectable computation graph that several executors run](ADR-0012-pipeline-is-a-computation-graph.md) - draft: one graph, many interpreters
* [ADR-0013 Events observe the compiler; they do not carry its dependencies](ADR-0013-events-observe-not-drive.md) - draft: no event spaghetti

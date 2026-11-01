These unchanged browser worker/policy files are from repository commit
`6522494` (2.31.1). They exercise the browser code that can stay loaded after an
unpacked extension's desktop installation has been upgraded. The regression
test verifies zero-budget blocking without requiring an extension reload.

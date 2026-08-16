# Recording examples

One worked example per opportunity type, showing the level of detail a useful
entry carries. A description that could have been written without doing the
work ("this function is long") is worth little; one that says what the work
revealed is worth reading months later.

**Reached green, skipped the refactor:**
```bash
boy-scout-record \
  --type skipped_refactor \
  --file src/billing/invoice.py \
  --lines 120-165 \
  --description "apply_discount() passed its new test as a fourth branch in the same if-chain; the chain wants to be a strategy lookup but the change was already large" \
  --severity medium \
  --context "Replace the if-chain with a DISCOUNT_RULES dict keyed by discount kind"
```

**Understanding it cost too much:**
```bash
boy-scout-record \
  --type comprehension_cost \
  --file src/auth/session.rs \
  --lines 44-70 \
  --description "Had to read session.rs, token_store.rs and clock.rs to find out that refresh() returns None on an expired token rather than an error" \
  --severity high \
  --context "Return an explicit Result<Token, SessionExpired> so the outcome is readable at the call site"
```

**A compromise made in this task:**
```bash
boy-scout-record \
  --type self_inflicted_debt \
  --file src/report/render.ts \
  --lines 88 \
  --description "Read the locale from the module-level config instead of threading it through renderRow(), to keep this diff to one file" \
  --severity medium \
  --context "Thread locale from buildReport() down to renderRow() and drop the module-level read"
```

**A test that is a problem in itself:**
```bash
boy-scout-record \
  --type test_smell \
  --file tests/test_checkout.py \
  --lines 30-95 \
  --description "test_checkout_flow mocks the repository, the clock and the mailer, so it asserts on call order rather than on the order being placed; it passes when the behaviour is wrong" \
  --severity high \
  --context "Use a real in-memory repository and a fixed clock; assert on the resulting order"
```

**The same region, again:**
```bash
boy-scout-record \
  --type repeated_friction \
  --file src/api/handlers.go \
  --description "Third session in a row that adding an endpoint required editing this file plus routes.go plus errors.go in lockstep" \
  --severity high \
  --context "The three files share one concept; consider a per-endpoint module that owns its route, handler and errors"
```

**Duplicated parsing logic:**
```bash
boy-scout-record \
  --type duplication \
  --file src/routes/auth.rs \
  --lines 88-104 \
  --description "JSON body parsing logic duplicated from src/routes/users.rs:45-61" \
  --severity medium \
  --context "Extract to a shared parse_json_body<T>() helper in src/util/http.rs"
```

**Function doing too much:**
```bash
boy-scout-record \
  --type function_size \
  --file src/compiler/lower.elm \
  --lines 200-280 \
  --description "lowerExpr handles literals, lambdas, and let-bindings in a single 80-line match" \
  --severity medium \
  --context "Split into lowerLiteral, lowerLambda, lowerLet following the existing pattern"
```

**Misleading name:**
```bash
boy-scout-record \
  --type naming \
  --file src/pipeline/process.ts \
  --lines 34 \
  --description "Variable 'data' holds a validated UserProfile, not raw data — rename to userProfile" \
  --severity low
```

**Missing tests:**
```bash
boy-scout-record \
  --type test_coverage \
  --file src/billing/invoice.py \
  --description "Invoice.apply_discount() has no tests; edge cases around negative discounts are untested" \
  --severity high
```

**Leaky abstraction:**
```bash
boy-scout-record \
  --type wrong_abstraction \
  --file src/storage/repo.rs \
  --lines 12-40 \
  --description "UserRepo returns raw SQL rows, so callers depend on the schema" \
  --severity high \
  --context "Map rows to a User domain type at the repo boundary"
```

**Dead code:**
```bash
boy-scout-record \
  --type dead_code \
  --file src/legacy/parser.js \
  --description "Commented-out v1 parser left below the v2 implementation" \
  --severity low
```


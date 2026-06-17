from aleph_coldbackup.names import safe_component, PathAllocator


def test_keeps_unicode_and_dotfiles():
    assert safe_component("YMD РЖД.xlsx", "x") == "YMD РЖД.xlsx"
    assert safe_component(".DS_Store", "x") == ".DS_Store"


def test_replaces_separators_and_controls():
    assert safe_component("a/b\\c", "x") == "a_b_c"
    assert safe_component("tab\tend", "x") == "tab_end"


def test_reserved_and_empty_use_fallback():
    assert safe_component("", "FALLBACK") == "FALLBACK"
    assert safe_component(None, "FALLBACK") == "FALLBACK"
    assert safe_component(".", "FALLBACK") == "FALLBACK"
    assert safe_component("..", "FALLBACK") == "FALLBACK"


def test_clamps_length():
    assert len(safe_component("a" * 500, "x")) == 255


def test_allocator_disambiguates_collisions():
    alloc = PathAllocator()
    n1, r1 = alloc.allocate("dir", "report.pdf", "abcdef1234567890")
    n2, r2 = alloc.allocate("dir", "report.pdf", "0011223344556677")
    assert (n1, r1) == ("report.pdf", False)
    assert (n2, r2) == ("report-00112233.pdf", True)


def test_allocator_collision_without_extension():
    alloc = PathAllocator()
    alloc.allocate("d", "README", "aaaaaaaa11111111")
    n2, r2 = alloc.allocate("d", "README", "bbbbbbbb22222222")
    assert (n2, r2) == ("README-bbbbbbbb", True)


def test_allocator_double_collision_appends_counter():
    alloc = PathAllocator()
    alloc.allocate("d", "a.txt", "deadbeefdeadbeef")
    n2, _ = alloc.allocate("d", "a.txt", "cafebabecafebabe")
    n3, _ = alloc.allocate("d", "a.txt", "cafebabecafebabe")  # same disambiguator
    assert n2 == "a-cafebabe.txt"
    assert n3 == "a-cafebabe-1.txt"


def test_allocator_separate_dirs_independent():
    alloc = PathAllocator()
    assert alloc.allocate("d1", "x", "h1")[0] == "x"
    assert alloc.allocate("d2", "x", "h2")[0] == "x"

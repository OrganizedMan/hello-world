from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_family_room_returns_not_blocking_validation_and_hash():
    r = client.get("/api/family-room")
    assert r.status_code == 200
    body = r.json()
    assert body["validation"]["is_blocking"] is False
    assert len(body["geometry_hash"]) == 64
    wall_ids = {w["id"] for w in body["walls"]}
    assert wall_ids == {"LIVING_ROOM.EAST", "LIVING_ROOM.SOUTH"}


def test_family_room_east_wall_topology_in_api_response():
    body = client.get("/api/family-room").json()
    east = next(w for w in body["walls"] if w["id"] == "LIVING_ROOM.EAST")
    assert [o["kind"] for o in east["openings"]] == ["window", "unframed"]
    assert east["openings"][1]["connects"] == ["LIVING_ROOM", "MUDROOM"]


def test_family_room_south_wall_has_single_5ft_opening():
    body = client.get("/api/family-room").json()
    south = next(w for w in body["walls"] if w["id"] == "LIVING_ROOM.SOUTH")
    assert len(south["openings"]) == 1
    assert south["openings"][0]["width"]["display"] == "5'"


def test_geometry_hash_is_stable_across_requests():
    h1 = client.get("/api/family-room").json()["geometry_hash"]
    h2 = client.get("/api/family-room").json()["geometry_hash"]
    assert h1 == h2


def test_mesh_endpoint_returns_nonempty_geometry_for_both_walls():
    r = client.get("/api/family-room/mesh")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"LIVING_ROOM.EAST", "LIVING_ROOM.SOUTH"}
    for wall_id, mesh in body.items():
        assert len(mesh["vertices"]) > 0
        assert len(mesh["triangles"]) > 0
        assert len(mesh["vertices"][0]) == 3


def test_tiers_endpoint_reports_a_for_originals_and_c_for_degraded():
    r = client.get("/api/tiers")
    assert r.status_code == 200
    body = r.json()
    assert body["a1"]["tier"] == "A"
    assert body["attic"]["tier"] == "A"
    assert body["degraded"]["tier"] == "C"


def test_source_image_returns_png():
    r = client.get("/api/source-image/a1")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_source_image_unknown_key_is_404():
    r = client.get("/api/source-image/nope")
    assert r.status_code == 404


def test_cors_restricted_to_dev_server_origin():
    r = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"

    r2 = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r2.headers


def test_extracted_source_returns_proposed_walls_with_matches_and_hash():
    r = client.get("/api/family-room?source=extracted")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "extracted"
    assert len(body["geometry_hash"]) == 64
    assert all(w["provenance_state"] == "PROPOSED" for w in body["walls"])
    assert body["dimension_matches"]
    assert all("error_in" in m for m in body["dimension_matches"])


def test_extracted_and_hand_traced_geometry_hashes_match():
    """The Stage 1 gate, visible through the API: real extraction from the
    PDF reproduces the exact same geometry hash as the Stage-0 hand-traced
    model. The hash deliberately excludes provenance (see geometry.hashing's
    wall_canonical_dict) so this is a genuine shape-identity result, not an
    artifact of both sources happening to carry similar metadata."""
    hand_traced = client.get("/api/family-room?source=hand_traced").json()
    extracted = client.get("/api/family-room?source=extracted").json()
    assert hand_traced["source"] == "hand_traced"
    assert len(hand_traced["geometry_hash"]) == 64
    assert hand_traced["geometry_hash"] == extracted["geometry_hash"]


def test_extracted_mesh_endpoint_returns_nonempty_geometry():
    r = client.get("/api/family-room/mesh?source=extracted")
    assert r.status_code == 200
    body = r.json()
    # The extracted source additionally carries the kitchen island (a
    # second, independent extraction technique) alongside the two walls.
    assert set(body) == {"LIVING_ROOM.EAST", "LIVING_ROOM.SOUTH", "KITCHEN.ISLAND"}


def test_unknown_source_is_400():
    r = client.get("/api/family-room?source=bogus")
    assert r.status_code == 400


def test_extracted_source_includes_kitchen_island_fixture():
    r = client.get("/api/family-room?source=extracted")
    body = r.json()
    assert "fixtures" in body
    island = body["fixtures"][0]
    assert island["id"] == "KITCHEN.ISLAND"
    assert island["width"]["display"] == "8'-7\""
    assert island["depth"]["display"] == "4'-3\""
    assert island["provenance_state"] == "PROPOSED"
    assert island["match_quality"]["width_error_in"] < 1.0


def test_hand_traced_source_has_no_fixtures_key():
    body = client.get("/api/family-room?source=hand_traced").json()
    assert "fixtures" not in body


def test_hand_traced_mesh_has_no_kitchen_island():
    body = client.get("/api/family-room/mesh?source=hand_traced").json()
    assert "KITCHEN.ISLAND" not in body

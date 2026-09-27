PRAGMA foreign_keys = ON;

CREATE TABLE build_metadata (
    build_id TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    source_count INTEGER NOT NULL CHECK (source_count >= 0)
);

CREATE TABLE raw_record (
    raw_record_id INTEGER PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    resource_kind TEXT NOT NULL CHECK (
        resource_kind IN ('item', 'quest_item', 'pet', 'title', 'ride')
    ),
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    raw_value TEXT NOT NULL,
    raw_values_json TEXT NOT NULL CHECK (json_valid(raw_values_json))
);

CREATE INDEX raw_record_source_idx
    ON raw_record(source_file, source_row);

CREATE TABLE resource (
    resource_kind TEXT NOT NULL CHECK (
        resource_kind IN ('item', 'quest_item', 'pet', 'title', 'ride')
    ),
    resource_id INTEGER NOT NULL CHECK (resource_id >= 0),
    display_name TEXT NOT NULL,
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    selected_source_file TEXT NOT NULL,
    selected_source_row INTEGER NOT NULL CHECK (selected_source_row > 0),
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    raw_values_json TEXT NOT NULL CHECK (json_valid(raw_values_json)),
    PRIMARY KEY (resource_kind, resource_id)
);

CREATE TABLE resource_source (
    resource_kind TEXT NOT NULL,
    resource_id INTEGER NOT NULL,
    raw_record_id INTEGER NOT NULL REFERENCES raw_record(raw_record_id),
    is_selected INTEGER NOT NULL CHECK (is_selected IN (0, 1)),
    PRIMARY KEY (resource_kind, resource_id, raw_record_id),
    FOREIGN KEY (resource_kind, resource_id)
        REFERENCES resource(resource_kind, resource_id)
);

CREATE TABLE title_attribute (
    resource_kind TEXT NOT NULL DEFAULT 'title' CHECK (
        resource_kind = 'title'
    ),
    title_id INTEGER NOT NULL,
    attribute_scope TEXT NOT NULL CHECK (
        attribute_scope IN ('active', 'passive')
    ),
    slot_no INTEGER NOT NULL CHECK (slot_no > 0),
    attribute_id INTEGER NOT NULL CHECK (attribute_id >= 0),
    attribute_name TEXT NOT NULL,
    value_kind TEXT NOT NULL CHECK (
        value_kind IN ('flat', 'percentage')
    ),
    raw_value INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    PRIMARY KEY (title_id, attribute_scope, slot_no),
    FOREIGN KEY (resource_kind, title_id)
        REFERENCES resource(resource_kind, resource_id)
);

CREATE INDEX title_attribute_title_idx
    ON title_attribute(title_id, attribute_scope, slot_no);

CREATE TABLE title_group (
    title_group_record_id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL CHECK (group_id >= 0),
    display_name TEXT NOT NULL,
    family_id INTEGER NOT NULL CHECK (family_id BETWEEN 1 AND 10),
    member_title_ids TEXT,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    UNIQUE (source_file, source_row)
);

CREATE INDEX title_group_family_idx
    ON title_group(family_id, display_name, group_id);

CREATE TABLE resource_relation (
    relation_id INTEGER PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    target_kind TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK (
        evidence_type IN ('source', 'mapped', 'curated', 'inferred')
    ),
    confidence REAL NOT NULL DEFAULT 1.0 CHECK (
        confidence >= 0.0 AND confidence <= 1.0
    ),
    source_file TEXT,
    source_row INTEGER,
    path_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(path_json)),
    raw_values_json TEXT CHECK (
        raw_values_json IS NULL OR json_valid(raw_values_json)
    ),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    UNIQUE (
        source_kind, source_id, target_kind, target_id, relation_type
    ),
    FOREIGN KEY (source_kind, source_id)
        REFERENCES resource(resource_kind, resource_id),
    FOREIGN KEY (target_kind, target_id)
        REFERENCES resource(resource_kind, resource_id)
);

CREATE TABLE parse_issue (
    issue_id INTEGER PRIMARY KEY,
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    raw_record_id INTEGER NOT NULL REFERENCES raw_record(raw_record_id),
    issue_code TEXT NOT NULL,
    detail TEXT NOT NULL
);

CREATE TABLE item_use_effect (
    effect_id INTEGER PRIMARY KEY,
    use_type_id INTEGER,
    parameters_json TEXT NOT NULL CHECK (json_valid(parameters_json)),
    description TEXT,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    raw_value TEXT NOT NULL,
    raw_values_json TEXT NOT NULL CHECK (json_valid(raw_values_json)),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id)
);

CREATE TABLE item_use_detail (
    effect_id INTEGER PRIMARY KEY REFERENCES item_use_effect(effect_id),
    detail_kind TEXT NOT NULL CHECK (
        detail_kind IN (
            'state_group', 'state_array', 'skill', 'collection',
            'avatar', 'loot_table', 'parameter'
        )
    ),
    display_name TEXT,
    description TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id)
);

CREATE TABLE item_use_link (
    resource_kind TEXT NOT NULL DEFAULT 'item' CHECK (resource_kind = 'item'),
    item_id INTEGER NOT NULL,
    effect_id INTEGER NOT NULL REFERENCES item_use_effect(effect_id),
    slot_no INTEGER NOT NULL,
    amount INTEGER,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    PRIMARY KEY (item_id, effect_id, slot_no),
    FOREIGN KEY (resource_kind, item_id)
        REFERENCES resource(resource_kind, resource_id)
);

CREATE TABLE item_text (
    text_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    raw_value TEXT NOT NULL,
    raw_values_json TEXT NOT NULL CHECK (json_valid(raw_values_json)),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id)
);

CREATE TABLE item_type (
    item_type_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    note TEXT,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    raw_value TEXT NOT NULL,
    raw_values_json TEXT NOT NULL CHECK (json_valid(raw_values_json)),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id)
);

CREATE TABLE ride_skill (
    skill_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT,
    internal_note TEXT,
    icon_key TEXT,
    definition_source_type TEXT NOT NULL CHECK (
        definition_source_type IN ('car_skill', 'npc_skill')
    ),
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    description_source_file TEXT,
    description_source_row INTEGER CHECK (
        description_source_row IS NULL OR description_source_row > 0
    ),
    raw_values_json TEXT NOT NULL CHECK (json_valid(raw_values_json)),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id)
);

-- skill_id intentionally has no foreign key: unresolved source references must
-- remain visible for quality reporting instead of being silently discarded.
CREATE TABLE ride_skill_link (
    resource_kind TEXT NOT NULL DEFAULT 'ride' CHECK (resource_kind = 'ride'),
    ride_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL CHECK (skill_id >= 0),
    slot_no INTEGER NOT NULL CHECK (slot_no BETWEEN 1 AND 6),
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    raw_value TEXT NOT NULL,
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    PRIMARY KEY (ride_id, slot_no),
    FOREIGN KEY (resource_kind, ride_id)
        REFERENCES resource(resource_kind, resource_id)
);

CREATE INDEX ride_skill_link_skill_idx
    ON ride_skill_link(skill_id);

CREATE TABLE pet_attribute_template (
    template_id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    strength INTEGER,
    physique INTEGER,
    yuan_spirit INTEGER,
    sinew INTEGER,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    raw_value TEXT NOT NULL,
    raw_values_json TEXT NOT NULL CHECK (json_valid(raw_values_json)),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id)
);

CREATE TABLE quest_resource_link (
    link_id INTEGER PRIMARY KEY,
    resource_kind TEXT NOT NULL,
    resource_id INTEGER NOT NULL,
    quest_id INTEGER NOT NULL CHECK (quest_id > 0),
    quest_name TEXT NOT NULL,
    relation_type TEXT NOT NULL CHECK (
        relation_type IN (
            'reward', 'required', 'objective', 'accept_endpoint',
            'submit_endpoint', 'title_reward', 'pet_reward'
        )
    ),
    amount INTEGER,
    quest_site_path TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_row INTEGER NOT NULL CHECK (source_row > 0),
    build_id TEXT NOT NULL REFERENCES build_metadata(build_id),
    UNIQUE (resource_kind, resource_id, quest_id, relation_type),
    FOREIGN KEY (resource_kind, resource_id)
        REFERENCES resource(resource_kind, resource_id)
);

CREATE INDEX quest_resource_link_resource_idx
    ON quest_resource_link(resource_kind, resource_id);

CREATE INDEX quest_resource_link_quest_idx
    ON quest_resource_link(quest_id);

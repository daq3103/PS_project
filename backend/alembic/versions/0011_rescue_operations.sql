
CREATE TABLE rescue_funds (
	title VARCHAR(150) NOT NULL,
	purpose TEXT NOT NULL,
	surplus_policy TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	public_report JSONB,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)

;
CREATE TABLE rescue_locations (
	name VARCHAR(100) NOT NULL,
	kind VARCHAR(20) NOT NULL,
	species VARCHAR(10) NOT NULL,
	capacity INTEGER NOT NULL,
	private_contact TEXT NOT NULL,
	available_from TIMESTAMP WITH TIME ZONE,
	available_until TIMESTAMP WITH TIME ZONE,
	active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_rescue_capacity CHECK (capacity > 0)
)

;
CREATE TABLE rescue_operation_receipts (
	scope VARCHAR(100) NOT NULL,
	key VARCHAR(100) NOT NULL,
	digest VARCHAR(64) NOT NULL,
	result JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)

;
CREATE TABLE rescue_audit (
	actor_id UUID,
	resource_id UUID NOT NULL,
	action VARCHAR(40) NOT NULL,
	details JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_cases (
	code VARCHAR(30) NOT NULL,
	summary TEXT NOT NULL,
	coordinator_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code),
	FOREIGN KEY(coordinator_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_expenses (
	fund_id UUID NOT NULL,
	requester_id UUID NOT NULL,
	approver_id UUID,
	amount BIGINT NOT NULL,
	purpose TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	payment_reference VARCHAR(160),
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (amount > 0),
	CHECK (approver_id IS NULL OR approver_id <> requester_id),
	FOREIGN KEY(fund_id) REFERENCES rescue_funds (id),
	FOREIGN KEY(requester_id) REFERENCES users (id),
	FOREIGN KEY(approver_id) REFERENCES users (id),
	UNIQUE (payment_reference)
)

;
CREATE TABLE rescue_ledger (
	fund_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	kind VARCHAR(30) NOT NULL,
	amount BIGINT NOT NULL,
	reference VARCHAR(180) NOT NULL,
	donor_name VARCHAR(100),
	anonymous BOOLEAN NOT NULL,
	note TEXT NOT NULL,
	reverses_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (amount > 0),
	FOREIGN KEY(fund_id) REFERENCES rescue_funds (id),
	FOREIGN KEY(actor_id) REFERENCES users (id),
	UNIQUE (reference),
	FOREIGN KEY(reverses_id) REFERENCES rescue_ledger (id)
)

;
CREATE TABLE rescue_publications (
	kind VARCHAR(20) NOT NULL,
	resource_id UUID NOT NULL,
	version INTEGER NOT NULL,
	approved_by UUID NOT NULL,
	payload JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(approved_by) REFERENCES users (id)
)

;
CREATE TABLE rescue_supply_receipts (
	name VARCHAR(150) NOT NULL,
	quantity INTEGER NOT NULL,
	accepted_quantity INTEGER NOT NULL,
	unit VARCHAR(30) NOT NULL,
	reference VARCHAR(160) NOT NULL,
	expiry_at TIMESTAMP WITH TIME ZONE,
	note TEXT NOT NULL,
	actor_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (quantity > 0 AND accepted_quantity >= 0 AND accepted_quantity <= quantity),
	UNIQUE (reference),
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_animals (
	code VARCHAR(30) NOT NULL,
	slug VARCHAR(180) NOT NULL,
	name VARCHAR(100) NOT NULL,
	species VARCHAR(10) NOT NULL,
	sex VARCHAR(10) NOT NULL,
	age_months INTEGER,
	story TEXT NOT NULL,
	public_area VARCHAR(100) NOT NULL,
	care_summary TEXT NOT NULL,
	adoption_state VARCHAR(20) NOT NULL,
	ownership_hold BOOLEAN NOT NULL,
	publication JSONB,
	published_at TIMESTAMP WITH TIME ZONE,
	post_id UUID,
	version INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (species IN ('dog','cat')),
	CHECK (age_months IS NULL OR age_months >= 0),
	UNIQUE (code),
	UNIQUE (slug),
	UNIQUE (post_id),
	FOREIGN KEY(post_id) REFERENCES community_posts (id)
)

;
CREATE TABLE rescue_reports (
	code VARCHAR(30) NOT NULL,
	user_id UUID,
	session_hash VARCHAR(64),
	description TEXT NOT NULL,
	species VARCHAR(10) NOT NULL,
	count_estimate INTEGER NOT NULL,
	seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
	private_location TEXT NOT NULL,
	private_contact VARCHAR(200) NOT NULL,
	status VARCHAR(30) NOT NULL,
	urgency VARCHAR(20) NOT NULL,
	case_id UUID,
	assignee_id UUID,
	acknowledged_at TIMESTAMP WITH TIME ZONE,
	resolution TEXT,
	version INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(case_id) REFERENCES rescue_cases (id),
	FOREIGN KEY(assignee_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_episodes (
	animal_id UUID NOT NULL,
	case_id UUID,
	location_id UUID NOT NULL,
	assignee_id UUID NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ended_at TIMESTAMP WITH TIME ZONE,
	outcome VARCHAR(30),
	source_note TEXT NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(animal_id) REFERENCES rescue_animals (id),
	FOREIGN KEY(case_id) REFERENCES rescue_cases (id),
	FOREIGN KEY(location_id) REFERENCES rescue_locations (id),
	FOREIGN KEY(assignee_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_events (
	animal_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	kind VARCHAR(30) NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	note TEXT NOT NULL,
	details JSONB NOT NULL,
	public BOOLEAN NOT NULL,
	supersedes_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(animal_id) REFERENCES rescue_animals (id),
	FOREIGN KEY(actor_id) REFERENCES users (id),
	FOREIGN KEY(supersedes_id) REFERENCES rescue_events (id)
)

;
CREATE TABLE rescue_tasks (
	animal_id UUID NOT NULL,
	episode_id UUID,
	assignee_id UUID NOT NULL,
	title VARCHAR(200) NOT NULL,
	instructions TEXT NOT NULL,
	due_at TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(20) NOT NULL,
	occurrence_key VARCHAR(160) NOT NULL,
	completed_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(animal_id) REFERENCES rescue_animals (id),
	FOREIGN KEY(episode_id) REFERENCES rescue_episodes (id),
	FOREIGN KEY(assignee_id) REFERENCES users (id),
	UNIQUE (occurrence_key)
)

;
CREATE UNIQUE INDEX uq_rescue_operation_key ON rescue_operation_receipts (scope, key);CREATE UNIQUE INDEX uq_rescue_publication_version ON rescue_publications (kind, resource_id, version);CREATE UNIQUE INDEX uq_rescue_episode_open ON rescue_episodes (animal_id) WHERE ended_at IS NULL;


CREATE TABLE rescue_reminders (
	occurrence_key VARCHAR(200) NOT NULL,
	resource_id UUID NOT NULL,
	sent_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (occurrence_key)
)

;
CREATE TABLE rescue_supply_needs (
	title VARCHAR(150) NOT NULL,
	unit VARCHAR(30) NOT NULL,
	quantity INTEGER NOT NULL,
	instructions TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
)

;
CREATE TABLE rescue_assets (
	resource_kind VARCHAR(20) NOT NULL,
	resource_id UUID NOT NULL,
	uploader_id UUID NOT NULL,
	storage_key VARCHAR(100) NOT NULL,
	media_type VARCHAR(50) NOT NULL,
	size INTEGER NOT NULL,
	caption VARCHAR(200) NOT NULL,
	publication_allowed BOOLEAN NOT NULL,
	public BOOLEAN NOT NULL,
	deleted_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(uploader_id) REFERENCES users (id),
	UNIQUE (storage_key)
)

;
CREATE TABLE rescue_consents (
	user_id UUID NOT NULL,
	resource_id UUID NOT NULL,
	purpose VARCHAR(30) NOT NULL,
	policy_version VARCHAR(40) NOT NULL,
	allowed BOOLEAN NOT NULL,
	changed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_messages (
	resource_kind VARCHAR(20) NOT NULL,
	resource_id UUID NOT NULL,
	sender_id UUID NOT NULL,
	body TEXT NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(sender_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_partners (
	user_id UUID NOT NULL,
	kind VARCHAR(20) NOT NULL,
	name VARCHAR(150) NOT NULL,
	contact VARCHAR(200) NOT NULL,
	area VARCHAR(150) NOT NULL,
	conditions TEXT NOT NULL,
	species VARCHAR(10) NOT NULL,
	capacity INTEGER NOT NULL,
	available_from TIMESTAMP WITH TIME ZONE NOT NULL,
	available_until TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(20) NOT NULL,
	decision_note TEXT NOT NULL,
	location_id UUID,
	version INTEGER NOT NULL,
	proposed_update JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (capacity >= 0),
	CHECK (available_until > available_from),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(location_id) REFERENCES rescue_locations (id)
)

;
CREATE TABLE rescue_shifts (
	assignee_id UUID NOT NULL,
	backup_id UUID NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
	instructions TEXT NOT NULL,
	handover TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	version INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (ends_at > starts_at),
	FOREIGN KEY(assignee_id) REFERENCES users (id),
	FOREIGN KEY(backup_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_refunds (
	entry_id UUID NOT NULL,
	requester_id UUID NOT NULL,
	approver_id UUID,
	amount BIGINT NOT NULL,
	reason TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	reference VARCHAR(160),
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (amount > 0),
	CHECK (approver_id IS NULL OR approver_id <> requester_id),
	FOREIGN KEY(entry_id) REFERENCES rescue_ledger (id),
	FOREIGN KEY(requester_id) REFERENCES users (id),
	FOREIGN KEY(approver_id) REFERENCES users (id),
	UNIQUE (reference)
)

;
CREATE TABLE rescue_supply_movements (
	receipt_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	kind VARCHAR(20) NOT NULL,
	quantity INTEGER NOT NULL,
	reason TEXT NOT NULL,
	reference VARCHAR(160) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (quantity > 0),
	FOREIGN KEY(receipt_id) REFERENCES rescue_supply_receipts (id),
	FOREIGN KEY(actor_id) REFERENCES users (id),
	UNIQUE (reference)
)

;
CREATE TABLE rescue_supply_pledges (
	user_id UUID NOT NULL,
	need_id UUID NOT NULL,
	quantity INTEGER NOT NULL,
	contact VARCHAR(200) NOT NULL,
	status VARCHAR(20) NOT NULL,
	tracking_reference VARCHAR(160),
	receipt_id UUID,
	version INTEGER NOT NULL,
	shop_order_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (quantity > 0),
	FOREIGN KEY(user_id) REFERENCES users (id),
	FOREIGN KEY(need_id) REFERENCES rescue_supply_needs (id),
	UNIQUE (tracking_reference),
	UNIQUE (receipt_id),
	FOREIGN KEY(receipt_id) REFERENCES rescue_supply_receipts (id),
	UNIQUE (shop_order_id),
	FOREIGN KEY(shop_order_id) REFERENCES orders (id)
)

;
CREATE TABLE rescue_application_checks (
	application_id UUID NOT NULL,
	verified_by UUID,
	verified_at TIMESTAMP WITH TIME ZONE,
	contact_method VARCHAR(30) NOT NULL,
	verification_note TEXT NOT NULL,
	agreement TEXT NOT NULL,
	handover_at TIMESTAMP WITH TIME ZONE,
	handover_by UUID,
	recipient_confirmed BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (application_id),
	FOREIGN KEY(application_id) REFERENCES adoption_requests (id),
	FOREIGN KEY(verified_by) REFERENCES users (id),
	FOREIGN KEY(handover_by) REFERENCES users (id)
)

;
CREATE TABLE rescue_appointments (
	animal_id UUID NOT NULL,
	application_id UUID,
	organizer_id UUID NOT NULL,
	participant_id UUID NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
	kind VARCHAR(20) NOT NULL,
	location TEXT NOT NULL,
	status VARCHAR(20) NOT NULL,
	version INTEGER NOT NULL,
	change_reason TEXT NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (ends_at > starts_at),
	FOREIGN KEY(animal_id) REFERENCES rescue_animals (id),
	FOREIGN KEY(application_id) REFERENCES adoption_requests (id),
	FOREIGN KEY(organizer_id) REFERENCES users (id),
	FOREIGN KEY(participant_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_campaigns (
	fund_id UUID NOT NULL,
	animal_id UUID,
	target BIGINT NOT NULL,
	opens_at TIMESTAMP WITH TIME ZONE NOT NULL,
	closes_at TIMESTAMP WITH TIME ZONE NOT NULL,
	status VARCHAR(20) NOT NULL,
	surplus_action VARCHAR(20) NOT NULL,
	version INTEGER NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (target > 0 AND closes_at > opens_at),
	UNIQUE (fund_id),
	FOREIGN KEY(fund_id) REFERENCES rescue_funds (id),
	FOREIGN KEY(animal_id) REFERENCES rescue_animals (id)
)

;
CREATE TABLE rescue_subscriptions (
	animal_id UUID NOT NULL,
	user_id UUID NOT NULL,
	updates BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(animal_id) REFERENCES rescue_animals (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;
CREATE TABLE rescue_care_schedules (
	episode_id UUID NOT NULL,
	title VARCHAR(200) NOT NULL,
	instructions TEXT NOT NULL,
	interval_days INTEGER NOT NULL,
	next_at TIMESTAMP WITH TIME ZONE NOT NULL,
	until_at TIMESTAMP WITH TIME ZONE NOT NULL,
	active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (interval_days > 0),
	FOREIGN KEY(episode_id) REFERENCES rescue_episodes (id)
)

;
CREATE TABLE rescue_donation_intents (
	code VARCHAR(30) NOT NULL,
	campaign_id UUID NOT NULL,
	user_id UUID NOT NULL,
	amount BIGINT NOT NULL,
	anonymous BOOLEAN NOT NULL,
	status VARCHAR(30) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	purpose_snapshot JSONB NOT NULL,
	ledger_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (amount > 0),
	UNIQUE (code),
	FOREIGN KEY(campaign_id) REFERENCES rescue_campaigns (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	UNIQUE (ledger_id),
	FOREIGN KEY(ledger_id) REFERENCES rescue_ledger (id)
)

;
CREATE TABLE rescue_visit_slots (
	animal_id UUID NOT NULL,
	organizer_id UUID NOT NULL,
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
	location TEXT NOT NULL,
	appointment_id UUID,
	active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CHECK (ends_at > starts_at),
	FOREIGN KEY(animal_id) REFERENCES rescue_animals (id),
	FOREIGN KEY(organizer_id) REFERENCES users (id),
	UNIQUE (appointment_id),
	FOREIGN KEY(appointment_id) REFERENCES rescue_appointments (id)
)

;
CREATE TABLE rescue_donation_events (
	reference VARCHAR(160) NOT NULL,
	intent_id UUID,
	amount BIGINT NOT NULL,
	status VARCHAR(40) NOT NULL,
	digest VARCHAR(64) NOT NULL,
	note TEXT NOT NULL,
	resolved_by UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (reference),
	FOREIGN KEY(intent_id) REFERENCES rescue_donation_intents (id),
	FOREIGN KEY(resolved_by) REFERENCES users (id)
)

;
CREATE UNIQUE INDEX uq_rescue_consent ON rescue_consents (user_id, purpose, resource_id);CREATE INDEX ix_rescue_message_thread ON rescue_messages (resource_kind, resource_id, created_at);CREATE INDEX ix_rescue_shift_time ON rescue_shifts (assignee_id, starts_at);CREATE INDEX ix_rescue_appointment_time ON rescue_appointments (organizer_id, starts_at);CREATE UNIQUE INDEX uq_rescue_subscription ON rescue_subscriptions (animal_id, user_id);

-- Baseline: original schema supplied with the project plan (unchanged except BEGIN/COMMIT removed).
-- All fixes live in 0002_v2_fixes.sql so they can be reviewed as a diff.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE member_status AS ENUM ('invited','active','suspended','removed');
CREATE TYPE document_status AS ENUM ('draft','posted','partially_paid','paid','overdue','cancelled');
CREATE TYPE order_status AS ENUM ('draft','sent','accepted','rejected','expired','partially_fulfilled','fulfilled','converted','cancelled');
CREATE TYPE party_kind AS ENUM ('customer','supplier','both');
CREATE TYPE item_kind AS ENUM ('goods','service');
CREATE TYPE payment_direction AS ENUM ('in','out');
CREATE TYPE payment_method AS ENUM ('cash','bank_transfer','upi','card','cheque','other');
CREATE TYPE stock_movement_type AS ENUM ('opening','purchase_receipt','sale_issue','sale_return','purchase_return','transfer_in','transfer_out','adjustment','damage','wastage','stock_count');
CREATE TYPE journal_status AS ENUM ('draft','posted','reversed');
CREATE TYPE tax_registration_type AS ENUM ('regular','composition','unregistered','consumer','overseas','other');

-- Identity and tenancy
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL,
    phone text,
    full_name text NOT NULL,
    password_hash text,
    email_verified_at timestamptz,
    phone_verified_at timestamptz,
    is_platform_admin boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT true,
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX uq_users_phone ON users (phone) WHERE phone IS NOT NULL;

CREATE TABLE tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed')),
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE tenant_memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status member_status NOT NULL DEFAULT 'active',
    joined_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,user_id)
);

CREATE TABLE companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name text NOT NULL,
    legal_name text,
    trade_name text,
    gstin varchar(15),
    pan varchar(10),
    email text,
    phone text,
    website text,
    address_line1 text,
    address_line2 text,
    city text,
    district text,
    state_code varchar(2),
    state_name text,
    postal_code text,
    country_code char(2) NOT NULL DEFAULT 'IN',
    currency_code char(3) NOT NULL DEFAULT 'INR',
    financial_year_start_month smallint NOT NULL DEFAULT 4 CHECK (financial_year_start_month BETWEEN 1 AND 12),
    timezone text NOT NULL DEFAULT 'Asia/Kolkata',
    logo_object_key text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id)
);
CREATE INDEX idx_companies_tenant ON companies(tenant_id);

CREATE TABLE company_memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status member_status NOT NULL DEFAULT 'active',
    is_owner boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,user_id),
    FOREIGN KEY (tenant_id,company_id) REFERENCES companies(tenant_id,id) ON DELETE CASCADE
);

CREATE TABLE roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name text NOT NULL,
    description text,
    is_system_role boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,name),
    UNIQUE (tenant_id,id)
);
CREATE TABLE permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    description text NOT NULL
);
CREATE TABLE role_permissions (
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id,permission_id)
);
CREATE TABLE company_member_roles (
    company_membership_id uuid NOT NULL REFERENCES company_memberships(id) ON DELETE CASCADE,
    role_id uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (company_membership_id,role_id)
);

-- Company configuration, fiscal periods and numbering
CREATE TABLE company_settings (
    company_id uuid PRIMARY KEY REFERENCES companies(id) ON DELETE CASCADE,
    settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    default_tax_mode text NOT NULL DEFAULT 'gst' CHECK (default_tax_mode IN ('gst','non_gst')),
    allow_negative_stock boolean NOT NULL DEFAULT false,
    stock_valuation_method text NOT NULL DEFAULT 'weighted_average'
        CHECK (stock_valuation_method IN ('weighted_average','fifo')),
    invoice_terms text,
    invoice_notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE financial_periods (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    starts_on date NOT NULL,
    ends_on date NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closing','closed')),
    closed_at timestamptz,
    closed_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_on >= starts_on),
    UNIQUE (company_id,name),
    UNIQUE (company_id,id)
);
CREATE TABLE document_sequences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    document_type text NOT NULL,
    financial_period_id uuid REFERENCES financial_periods(id) ON DELETE RESTRICT,
    prefix text NOT NULL DEFAULT '',
    next_number bigint NOT NULL DEFAULT 1 CHECK (next_number > 0),
    padding smallint NOT NULL DEFAULT 0 CHECK (padding BETWEEN 0 AND 20),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,document_type,financial_period_id)
);

-- Parties and addresses
CREATE TABLE parties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code text,
    name text NOT NULL,
    legal_name text,
    kind party_kind NOT NULL,
    gstin varchar(15),
    pan varchar(10),
    tax_registration_type tax_registration_type NOT NULL DEFAULT 'unregistered',
    email text,
    phone text,
    alternate_phone text,
    opening_balance numeric(19,4) NOT NULL DEFAULT 0,
    opening_balance_side text CHECK (opening_balance_side IN ('receivable','payable','none')),
    credit_limit numeric(19,4),
    payment_terms_days integer NOT NULL DEFAULT 0 CHECK (payment_terms_days >= 0),
    notes text,
    is_archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,code)
);
CREATE INDEX idx_parties_company_name ON parties(company_id,lower(name));
CREATE INDEX idx_parties_company_phone ON parties(company_id,phone);
CREATE TABLE party_addresses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid NOT NULL,
    address_type text NOT NULL CHECK (address_type IN ('billing','shipping','other')),
    line1 text NOT NULL,
    line2 text,
    city text,
    district text,
    state_code varchar(2),
    state_name text,
    postal_code text,
    country_code char(2) NOT NULL DEFAULT 'IN',
    is_default boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE CASCADE
);

-- Catalog, units and tax
CREATE TABLE units (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    abbreviation text NOT NULL,
    decimal_places smallint NOT NULL DEFAULT 2 CHECK (decimal_places BETWEEN 0 AND 6),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,name),
    UNIQUE (company_id,abbreviation),
    UNIQUE (company_id,id)
);
CREATE TABLE unit_conversions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    from_unit_id uuid NOT NULL,
    to_unit_id uuid NOT NULL,
    factor numeric(20,8) NOT NULL CHECK (factor > 0),
    UNIQUE (company_id,from_unit_id,to_unit_id),
    FOREIGN KEY (company_id,from_unit_id) REFERENCES units(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,to_unit_id) REFERENCES units(company_id,id) ON DELETE RESTRICT,
    CHECK (from_unit_id <> to_unit_id)
);
CREATE TABLE item_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    parent_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,name),
    UNIQUE (company_id,id),
    FOREIGN KEY (company_id,parent_id) REFERENCES item_categories(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE tax_rates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    tax_type text NOT NULL DEFAULT 'gst' CHECK (tax_type IN ('gst','cess','other','exempt','nil_rated')),
    rate_percent numeric(7,4) NOT NULL DEFAULT 0 CHECK (rate_percent >= 0 AND rate_percent <= 100),
    cgst_percent numeric(7,4) NOT NULL DEFAULT 0 CHECK (cgst_percent >= 0 AND cgst_percent <= 100),
    sgst_percent numeric(7,4) NOT NULL DEFAULT 0 CHECK (sgst_percent >= 0 AND sgst_percent <= 100),
    igst_percent numeric(7,4) NOT NULL DEFAULT 0 CHECK (igst_percent >= 0 AND igst_percent <= 100),
    cess_percent numeric(7,4) NOT NULL DEFAULT 0 CHECK (cess_percent >= 0 AND cess_percent <= 100),
    effective_from date,
    effective_to date,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,name),
    UNIQUE (company_id,id),
    CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);
CREATE TABLE items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_id uuid,
    unit_id uuid NOT NULL,
    tax_rate_id uuid,
    sku text,
    name text NOT NULL,
    description text,
    kind item_kind NOT NULL DEFAULT 'goods',
    hsn_sac text,
    barcode text,
    sale_price numeric(19,4) NOT NULL DEFAULT 0 CHECK (sale_price >= 0),
    purchase_price numeric(19,4) NOT NULL DEFAULT 0 CHECK (purchase_price >= 0),
    opening_quantity numeric(20,6) NOT NULL DEFAULT 0,
    reorder_level numeric(20,6) NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
    sale_price_includes_tax boolean NOT NULL DEFAULT false,
    purchase_price_includes_tax boolean NOT NULL DEFAULT false,
    track_inventory boolean NOT NULL DEFAULT true,
    is_archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,sku),
    FOREIGN KEY (company_id,category_id) REFERENCES item_categories(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,unit_id) REFERENCES units(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,tax_rate_id) REFERENCES tax_rates(company_id,id) ON DELETE RESTRICT
);
CREATE INDEX idx_items_company_name ON items(company_id,lower(name));
CREATE INDEX idx_items_company_barcode ON items(company_id,barcode);
CREATE TABLE item_barcodes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    item_id uuid NOT NULL,
    barcode text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,barcode),
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE CASCADE
);
CREATE TABLE item_prices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    item_id uuid NOT NULL,
    price_type text NOT NULL CHECK (price_type IN ('sale','purchase','wholesale','retail','custom')),
    price numeric(19,4) NOT NULL CHECK (price >= 0),
    party_id uuid,
    valid_from date,
    valid_to date,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT,
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

-- Warehouses and stock ledger
CREATE TABLE warehouses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    code text,
    address text,
    is_default boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,name),
    UNIQUE (company_id,code)
);
CREATE TABLE stock_movements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    item_id uuid NOT NULL,
    warehouse_id uuid NOT NULL,
    movement_type stock_movement_type NOT NULL,
    quantity_delta numeric(20,6) NOT NULL CHECK (quantity_delta <> 0),
    unit_cost numeric(19,4) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    reference_type text,
    reference_id uuid,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT
);
CREATE INDEX idx_stock_movements_item_date ON stock_movements(company_id,item_id,occurred_at);
CREATE INDEX idx_stock_movements_warehouse_date ON stock_movements(company_id,warehouse_id,occurred_at);
CREATE TABLE stock_balances (
    company_id uuid NOT NULL,
    item_id uuid NOT NULL,
    warehouse_id uuid NOT NULL,
    quantity_on_hand numeric(20,6) NOT NULL DEFAULT 0,
    average_cost numeric(19,4) NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id,item_id,warehouse_id),
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE CASCADE
);
CREATE TABLE stock_transfers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    transfer_number text NOT NULL,
    source_warehouse_id uuid NOT NULL,
    destination_warehouse_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','posted','cancelled')),
    transfer_date date NOT NULL,
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
	UNIQUE (company_id, id),
    UNIQUE (company_id,transfer_number),
    FOREIGN KEY (company_id,source_warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,destination_warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT,
    CHECK (source_warehouse_id <> destination_warehouse_id)
);
CREATE TABLE stock_transfer_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    transfer_id uuid NOT NULL,
    item_id uuid NOT NULL,
    quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
    unit_cost numeric(19,4) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    FOREIGN KEY (company_id,transfer_id) REFERENCES stock_transfers(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE stock_counts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    warehouse_id uuid NOT NULL,
    count_number text NOT NULL,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','counted','approved','posted','cancelled')),
    count_date date NOT NULL,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    approved_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,count_number),
    UNIQUE (company_id,id),
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE stock_count_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    stock_count_id uuid NOT NULL,
    item_id uuid NOT NULL,
    expected_quantity numeric(20,6) NOT NULL,
    counted_quantity numeric(20,6) NOT NULL CHECK (counted_quantity >= 0),
    difference_quantity numeric(20,6) GENERATED ALWAYS AS (counted_quantity - expected_quantity) STORED,
    FOREIGN KEY (company_id,stock_count_id) REFERENCES stock_counts(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    UNIQUE (stock_count_id,item_id)
);

-- Sales documents
CREATE TABLE sales_invoices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid,
    financial_period_id uuid REFERENCES financial_periods(id) ON DELETE RESTRICT,
    invoice_number text NOT NULL,
    invoice_date date NOT NULL,
    due_date date,
    status document_status NOT NULL DEFAULT 'draft',
    place_of_supply_state_code varchar(2),
    supply_type text NOT NULL DEFAULT 'intra_state' CHECK (supply_type IN ('intra_state','inter_state','export','other')),
    customer_name_snapshot text NOT NULL,
    customer_gstin_snapshot varchar(15),
    billing_address_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    shipping_address_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    subtotal numeric(19,4) NOT NULL DEFAULT 0,
    discount_total numeric(19,4) NOT NULL DEFAULT 0,
    taxable_total numeric(19,4) NOT NULL DEFAULT 0,
    cgst_total numeric(19,4) NOT NULL DEFAULT 0,
    sgst_total numeric(19,4) NOT NULL DEFAULT 0,
    igst_total numeric(19,4) NOT NULL DEFAULT 0,
    cess_total numeric(19,4) NOT NULL DEFAULT 0,
    other_charges numeric(19,4) NOT NULL DEFAULT 0,
    round_off numeric(19,4) NOT NULL DEFAULT 0,
    grand_total numeric(19,4) NOT NULL DEFAULT 0,
    paid_total numeric(19,4) NOT NULL DEFAULT 0,
    notes text,
    terms text,
    source_type text,
    source_id uuid,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_at timestamptz,
    cancelled_at timestamptz,
    cancellation_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,invoice_number),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT,
    CHECK (due_date IS NULL OR due_date >= invoice_date),
    CHECK (subtotal >= 0 AND discount_total >= 0 AND grand_total >= 0 AND paid_total >= 0)
);
CREATE INDEX idx_sales_invoice_date ON sales_invoices(company_id,invoice_date);
CREATE INDEX idx_sales_invoice_party ON sales_invoices(company_id,party_id,invoice_date);
CREATE INDEX idx_sales_invoice_status ON sales_invoices(company_id,status,invoice_date);
CREATE TABLE sales_invoice_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    invoice_id uuid NOT NULL,
    line_number integer NOT NULL,
    item_id uuid,
    item_name_snapshot text NOT NULL,
    sku_snapshot text,
    hsn_sac_snapshot text,
    unit_name_snapshot text NOT NULL,
    quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
    unit_price numeric(19,4) NOT NULL CHECK (unit_price >= 0),
    discount_percent numeric(7,4) NOT NULL DEFAULT 0 CHECK (discount_percent BETWEEN 0 AND 100),
    discount_amount numeric(19,4) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    taxable_amount numeric(19,4) NOT NULL DEFAULT 0,
    tax_rate_percent numeric(7,4) NOT NULL DEFAULT 0,
    cgst_amount numeric(19,4) NOT NULL DEFAULT 0,
    sgst_amount numeric(19,4) NOT NULL DEFAULT 0,
    igst_amount numeric(19,4) NOT NULL DEFAULT 0,
    cess_amount numeric(19,4) NOT NULL DEFAULT 0,
    line_total numeric(19,4) NOT NULL DEFAULT 0,
    warehouse_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id,invoice_id) REFERENCES sales_invoices(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT,
    UNIQUE (company_id,id),
    UNIQUE (invoice_id,line_number)
);
CREATE TABLE quotations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid,
    quotation_number text NOT NULL,
    quotation_date date NOT NULL,
    valid_until date,
    status order_status NOT NULL DEFAULT 'draft',
    customer_name_snapshot text NOT NULL,
    subtotal numeric(19,4) NOT NULL DEFAULT 0,
    tax_total numeric(19,4) NOT NULL DEFAULT 0,
    grand_total numeric(19,4) NOT NULL DEFAULT 0,
    converted_invoice_id uuid,
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,quotation_number),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,converted_invoice_id) REFERENCES sales_invoices(company_id,id) ON DELETE SET NULL
);
CREATE TABLE quotation_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    quotation_id uuid NOT NULL,
    line_number integer NOT NULL,
    item_id uuid,
    item_name_snapshot text NOT NULL,
    quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
    unit_price numeric(19,4) NOT NULL CHECK (unit_price >= 0),
    discount_amount numeric(19,4) NOT NULL DEFAULT 0,
    tax_rate_percent numeric(7,4) NOT NULL DEFAULT 0,
    line_total numeric(19,4) NOT NULL DEFAULT 0,
    FOREIGN KEY (company_id,quotation_id) REFERENCES quotations(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    UNIQUE (quotation_id,line_number)
);
CREATE TABLE sales_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid,
    order_number text NOT NULL,
    order_date date NOT NULL,
    expected_date date,
    status order_status NOT NULL DEFAULT 'draft',
    customer_name_snapshot text NOT NULL,
    grand_total numeric(19,4) NOT NULL DEFAULT 0,
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,order_number),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE sales_order_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    sales_order_id uuid NOT NULL,
    item_id uuid,
    item_name_snapshot text NOT NULL,
    ordered_quantity numeric(20,6) NOT NULL CHECK (ordered_quantity > 0),
    fulfilled_quantity numeric(20,6) NOT NULL DEFAULT 0 CHECK (fulfilled_quantity >= 0),
    unit_price numeric(19,4) NOT NULL CHECK (unit_price >= 0),
    line_total numeric(19,4) NOT NULL DEFAULT 0,
    FOREIGN KEY (company_id,sales_order_id) REFERENCES sales_orders(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    CHECK (fulfilled_quantity <= ordered_quantity)
);
CREATE TABLE delivery_challans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid,
    challan_number text NOT NULL,
    challan_date date NOT NULL,
    status order_status NOT NULL DEFAULT 'draft',
    customer_name_snapshot text NOT NULL,
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,challan_number),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE delivery_challan_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    challan_id uuid NOT NULL,
    item_id uuid,
    item_name_snapshot text NOT NULL,
    quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
    warehouse_id uuid,
    FOREIGN KEY (company_id,challan_id) REFERENCES delivery_challans(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT
);

-- Purchase documents
CREATE TABLE purchase_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid NOT NULL,
    order_number text NOT NULL,
    order_date date NOT NULL,
    expected_date date,
    status order_status NOT NULL DEFAULT 'draft',
    supplier_name_snapshot text NOT NULL,
    grand_total numeric(19,4) NOT NULL DEFAULT 0,
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,order_number),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE purchase_order_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    purchase_order_id uuid NOT NULL,
    item_id uuid,
    item_name_snapshot text NOT NULL,
    ordered_quantity numeric(20,6) NOT NULL CHECK (ordered_quantity > 0),
    received_quantity numeric(20,6) NOT NULL DEFAULT 0 CHECK (received_quantity >= 0),
    unit_cost numeric(19,4) NOT NULL CHECK (unit_cost >= 0),
    line_total numeric(19,4) NOT NULL DEFAULT 0,
    FOREIGN KEY (company_id,purchase_order_id) REFERENCES purchase_orders(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    CHECK (received_quantity <= ordered_quantity)
);
CREATE TABLE purchase_bills (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid NOT NULL,
    financial_period_id uuid REFERENCES financial_periods(id) ON DELETE RESTRICT,
    bill_number text NOT NULL,
    supplier_invoice_number text,
    bill_date date NOT NULL,
    due_date date,
    status document_status NOT NULL DEFAULT 'draft',
    supplier_name_snapshot text NOT NULL,
    supplier_gstin_snapshot varchar(15),
    subtotal numeric(19,4) NOT NULL DEFAULT 0,
    discount_total numeric(19,4) NOT NULL DEFAULT 0,
    taxable_total numeric(19,4) NOT NULL DEFAULT 0,
    cgst_total numeric(19,4) NOT NULL DEFAULT 0,
    sgst_total numeric(19,4) NOT NULL DEFAULT 0,
    igst_total numeric(19,4) NOT NULL DEFAULT 0,
    cess_total numeric(19,4) NOT NULL DEFAULT 0,
    other_charges numeric(19,4) NOT NULL DEFAULT 0,
    grand_total numeric(19,4) NOT NULL DEFAULT 0,
    paid_total numeric(19,4) NOT NULL DEFAULT 0,
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_at timestamptz,
    cancelled_at timestamptz,
    cancellation_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,bill_number),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT,
    CHECK (due_date IS NULL OR due_date >= bill_date),
    CHECK (grand_total >= 0 AND paid_total >= 0)
);
CREATE INDEX idx_purchase_bills_date ON purchase_bills(company_id,bill_date);
CREATE INDEX idx_purchase_bills_party ON purchase_bills(company_id,party_id,bill_date);
CREATE TABLE purchase_bill_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    purchase_bill_id uuid NOT NULL,
    line_number integer NOT NULL,
    item_id uuid,
    item_name_snapshot text NOT NULL,
    hsn_sac_snapshot text,
    unit_name_snapshot text NOT NULL,
    quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
    unit_cost numeric(19,4) NOT NULL CHECK (unit_cost >= 0),
    discount_amount numeric(19,4) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    taxable_amount numeric(19,4) NOT NULL DEFAULT 0,
    tax_rate_percent numeric(7,4) NOT NULL DEFAULT 0,
    cgst_amount numeric(19,4) NOT NULL DEFAULT 0,
    sgst_amount numeric(19,4) NOT NULL DEFAULT 0,
    igst_amount numeric(19,4) NOT NULL DEFAULT 0,
    cess_amount numeric(19,4) NOT NULL DEFAULT 0,
    line_total numeric(19,4) NOT NULL DEFAULT 0,
    warehouse_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id,purchase_bill_id) REFERENCES purchase_bills(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT,
    UNIQUE (company_id,id),
    UNIQUE (purchase_bill_id,line_number)
);

-- Credit/debit notes and returns
CREATE TABLE sales_returns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    original_invoice_id uuid NOT NULL,
    party_id uuid,
    return_number text NOT NULL,
    return_date date NOT NULL,
    status document_status NOT NULL DEFAULT 'draft',
    reason text,
    total_amount numeric(19,4) NOT NULL DEFAULT 0,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,return_number),
    FOREIGN KEY (company_id,original_invoice_id) REFERENCES sales_invoices(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE sales_return_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    sales_return_id uuid NOT NULL,
    original_invoice_line_id uuid NOT NULL,
    item_id uuid,
    quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
    line_total numeric(19,4) NOT NULL DEFAULT 0,
    warehouse_id uuid,
    FOREIGN KEY (company_id,sales_return_id) REFERENCES sales_returns(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,original_invoice_line_id) REFERENCES sales_invoice_lines(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE purchase_returns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    original_purchase_bill_id uuid NOT NULL,
    party_id uuid NOT NULL,
    return_number text NOT NULL,
    return_date date NOT NULL,
    status document_status NOT NULL DEFAULT 'draft',
    reason text,
    total_amount numeric(19,4) NOT NULL DEFAULT 0,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,return_number),
    FOREIGN KEY (company_id,original_purchase_bill_id) REFERENCES purchase_bills(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE purchase_return_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    purchase_return_id uuid NOT NULL,
    original_purchase_line_id uuid NOT NULL,
    item_id uuid,
    quantity numeric(20,6) NOT NULL CHECK (quantity > 0),
    line_total numeric(19,4) NOT NULL DEFAULT 0,
    warehouse_id uuid,
    FOREIGN KEY (company_id,purchase_return_id) REFERENCES purchase_returns(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,original_purchase_line_id) REFERENCES purchase_bill_lines(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,item_id) REFERENCES items(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,warehouse_id) REFERENCES warehouses(company_id,id) ON DELETE RESTRICT
);

-- Financial accounts and payments
CREATE TABLE payment_accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    account_type text NOT NULL CHECK (account_type IN ('cash','bank','upi','card_clearing','other')),
    bank_name text,
    account_number_masked text,
    opening_balance numeric(19,4) NOT NULL DEFAULT 0,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,name)
);
CREATE TABLE payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    party_id uuid,
    payment_account_id uuid NOT NULL,
    direction payment_direction NOT NULL,
    payment_number text NOT NULL,
    payment_date date NOT NULL,
    amount numeric(19,4) NOT NULL CHECK (amount > 0),
    method payment_method NOT NULL DEFAULT 'cash',
    reference_number text,
    status text NOT NULL DEFAULT 'posted' CHECK (status IN ('draft','posted','reversed')),
    notes text,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,payment_number),
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,payment_account_id) REFERENCES payment_accounts(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE payment_allocations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    payment_id uuid NOT NULL,
    sales_invoice_id uuid,
    purchase_bill_id uuid,
    amount numeric(19,4) NOT NULL CHECK (amount > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id,payment_id) REFERENCES payments(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,sales_invoice_id) REFERENCES sales_invoices(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,purchase_bill_id) REFERENCES purchase_bills(company_id,id) ON DELETE RESTRICT,
    CHECK (
        (sales_invoice_id IS NOT NULL AND purchase_bill_id IS NULL) OR
        (sales_invoice_id IS NULL AND purchase_bill_id IS NOT NULL)
    )
);
CREATE INDEX idx_payment_alloc_invoice ON payment_allocations(company_id,sales_invoice_id);
CREATE INDEX idx_payment_alloc_bill ON payment_allocations(company_id,purchase_bill_id);

-- Expenses and other income
CREATE TABLE expense_categories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    account_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,name)
);
CREATE TABLE expenses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    category_id uuid NOT NULL,
    payment_account_id uuid NOT NULL,
    expense_number text NOT NULL,
    expense_date date NOT NULL,
    payee text,
    amount numeric(19,4) NOT NULL CHECK (amount >= 0),
    tax_amount numeric(19,4) NOT NULL DEFAULT 0,
    description text,
    status text NOT NULL DEFAULT 'posted' CHECK (status IN ('draft','posted','cancelled')),
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,expense_number),
    FOREIGN KEY (company_id,category_id) REFERENCES expense_categories(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,payment_account_id) REFERENCES payment_accounts(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE other_income (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    payment_account_id uuid NOT NULL,
    income_number text NOT NULL,
    income_date date NOT NULL,
    category text NOT NULL,
    received_from text,
    amount numeric(19,4) NOT NULL CHECK (amount >= 0),
    notes text,
    status text NOT NULL DEFAULT 'posted' CHECK (status IN ('draft','posted','cancelled')),
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,income_number),
    FOREIGN KEY (company_id,payment_account_id) REFERENCES payment_accounts(company_id,id) ON DELETE RESTRICT
);

-- Double-entry accounting ledger
CREATE TABLE accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    code text NOT NULL,
    name text NOT NULL,
    account_type text NOT NULL CHECK (account_type IN ('asset','liability','equity','income','expense')),
    parent_account_id uuid,
    is_control_account boolean NOT NULL DEFAULT false,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,code),
    FOREIGN KEY (company_id,parent_account_id) REFERENCES accounts(company_id,id) ON DELETE RESTRICT
);
CREATE TABLE journal_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    financial_period_id uuid REFERENCES financial_periods(id) ON DELETE RESTRICT,
    entry_number text NOT NULL,
    entry_date date NOT NULL,
    description text,
    status journal_status NOT NULL DEFAULT 'draft',
    source_type text,
    source_id uuid,
    reversal_of_id uuid REFERENCES journal_entries(id) ON DELETE RESTRICT,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_by uuid REFERENCES users(id) ON DELETE SET NULL,
    posted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (company_id,id),
    UNIQUE (company_id,entry_number)
);
CREATE TABLE journal_lines (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    journal_entry_id uuid NOT NULL,
    line_number integer NOT NULL,
    account_id uuid NOT NULL,
    party_id uuid,
    description text,
    debit numeric(19,4) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit numeric(19,4) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (company_id,journal_entry_id) REFERENCES journal_entries(company_id,id) ON DELETE CASCADE,
    FOREIGN KEY (company_id,account_id) REFERENCES accounts(company_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (company_id,party_id) REFERENCES parties(company_id,id) ON DELETE RESTRICT,
    UNIQUE (journal_entry_id,line_number),
    CHECK ((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0))
);

-- Attachments, notifications, imports/exports and audit
CREATE TABLE attachments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    file_name text NOT NULL,
    content_type text NOT NULL,
    object_key text NOT NULL,
    file_size_bytes bigint NOT NULL CHECK (file_size_bytes >= 0),
    uploaded_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE message_outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    channel text NOT NULL CHECK (channel IN ('email','sms','whatsapp','webhook')),
    recipient text NOT NULL,
    template_key text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','sent','failed','cancelled')),
    attempt_count integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz,
    provider_message_id text,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);
CREATE INDEX idx_message_outbox_pending ON message_outbox(status,next_attempt_at);
CREATE TABLE import_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    entity_type text NOT NULL,
    file_name text NOT NULL,
    status text NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','validating','ready','processing','completed','failed')),
    total_rows integer NOT NULL DEFAULT 0,
    successful_rows integer NOT NULL DEFAULT 0,
    failed_rows integer NOT NULL DEFAULT 0,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE TABLE import_rows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    import_job_id uuid NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    row_number integer NOT NULL,
    raw_data jsonb NOT NULL,
    validation_errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','valid','imported','failed','skipped')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (import_job_id,row_number)
);
CREATE TABLE export_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    export_type text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','completed','failed','expired')),
    object_key text,
    expires_at timestamptz,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    error_message text
);
CREATE TABLE audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES tenants(id) ON DELETE SET NULL,
    company_id uuid REFERENCES companies(id) ON DELETE SET NULL,
    actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    request_id text,
    ip_address inet,
    user_agent text,
    before_data jsonb,
    after_data jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_company_created ON audit_events(company_id,created_at DESC);
CREATE INDEX idx_audit_entity ON audit_events(entity_type,entity_id);
CREATE TABLE idempotency_keys (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    response_status integer,
    response_body jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    UNIQUE (company_id,idempotency_key)
);

-- Helpful lookup indexes
CREATE INDEX idx_stock_transfers_date ON stock_transfers(company_id,transfer_date);
CREATE INDEX idx_payments_date ON payments(company_id,payment_date);
CREATE INDEX idx_expenses_date ON expenses(company_id,expense_date);
CREATE INDEX idx_journal_entries_date ON journal_entries(company_id,entry_date);
CREATE INDEX idx_journal_lines_account ON journal_lines(company_id,account_id);
CREATE INDEX idx_sales_returns_date ON sales_returns(company_id,return_date);
CREATE INDEX idx_purchase_returns_date ON purchase_returns(company_id,return_date);

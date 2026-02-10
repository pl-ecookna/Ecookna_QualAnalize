-- entechai.public.qual_analize_pos определение

-- Drop table

-- DROP TABLE entechai.public.qual_analize_pos;

CREATE TABLE entechai.public.qual_analize_pos (
	id serial DEFAULT nextval('qual_analize_pos_id_seq'::regclass) NOT NULL,
	date_created timestamptz,
	file_id int4,
	position_num varchar(255),
	position_formula varchar(255),
	position_raskl varchar(255),
	position_width int4,
	position_hight int4,
	position_width_round int4,
	position_hight_round int4,
	position_count int4,
	position_area float4,
	position_mass float4,
	position_formula_slip varchar(255),
	article_json json,
	f1 varchar(255),
	f2 varchar(255),
	cam_count int2,
	overall_status text,
	overall_message text,
	updated_at timestamptz DEFAULT now(),
	is_oytside bool,
	CONSTRAINT qual_analize_pos_pkey PRIMARY KEY (id)
);


-- entechai.public.qual_analize_pos внешние включи

ALTER TABLE entechai.public.qual_analize_pos ADD CONSTRAINT qual_analize_pos_file_id_foreign FOREIGN KEY (file_id) REFERENCES entechai.public.qual_analize_files(id);
-- entechai.public.qual_analize_files определение

-- Drop table

-- DROP TABLE entechai.public.qual_analize_files;

CREATE TABLE entechai.public.qual_analize_files (
	id serial DEFAULT nextval('qual_analize_files_id_seq'::regclass) NOT NULL,
	created_at timestamp,
	updated_at timestamp,
	file_name text,
	file_path text,
	responce text,
	tg_username text,
	tg_chatid int8,
	rules text,
	used_prompt text,
	full_raw text,
	total_items int4,
	issues_count int4,
	has_issues bool,
	analysis_status text,
	CONSTRAINT qual_analize_files_pkey PRIMARY KEY (id)
);

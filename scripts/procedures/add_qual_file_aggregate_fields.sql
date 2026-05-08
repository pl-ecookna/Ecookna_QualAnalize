ALTER TABLE public.qual_analize_files
  ADD COLUMN IF NOT EXISTS total_items int4,
  ADD COLUMN IF NOT EXISTS issues_count int4,
  ADD COLUMN IF NOT EXISTS has_issues bool,
  ADD COLUMN IF NOT EXISTS analysis_status text;

WITH file_stats AS (
  SELECT
    f.id AS file_id,
    count(DISTINCT p.id) AS total_items,
    count(DISTINCT CASE WHEN i.id IS NOT NULL THEN p.id END) AS issues_count
  FROM public.qual_analize_files f
  LEFT JOIN public.qual_analize_pos p
    ON p.file_id = f.id
  LEFT JOIN public.qual_analize_pos_issues i
    ON i.pos_id = p.id
  GROUP BY f.id
)
UPDATE public.qual_analize_files qf
SET
  total_items = fs.total_items,
  issues_count = fs.issues_count,
  has_issues = (fs.issues_count > 0),
  analysis_status = CASE
    WHEN fs.total_items = 0 THEN 'warning'
    WHEN fs.issues_count > 0 THEN 'issues_found'
    ELSE 'success'
  END
FROM file_stats fs
WHERE fs.file_id = qf.id
  AND (
    qf.total_items IS DISTINCT FROM fs.total_items
    OR qf.issues_count IS DISTINCT FROM fs.issues_count
    OR qf.has_issues IS DISTINCT FROM (fs.issues_count > 0)
    OR qf.analysis_status IS DISTINCT FROM CASE
      WHEN fs.total_items = 0 THEN 'warning'
      WHEN fs.issues_count > 0 THEN 'issues_found'
      ELSE 'success'
    END
  );

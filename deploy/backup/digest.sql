-- Row count and content hash per table; equal output means an identical restore.
SELECT string_agg(t || ':' || n || ':' || h, ' ' ORDER BY t) FROM (
  SELECT 'users' t, count(*) n, md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) h FROM users x
  UNION ALL SELECT 'test_scores', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM test_scores x
  UNION ALL SELECT 'dislikes', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM dislikes x
  UNION ALL SELECT 'reactions', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM reactions x
  UNION ALL SELECT 'matches', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM matches x
  UNION ALL SELECT 'invites', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM invites x
  UNION ALL SELECT 'sessions', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM sessions x
  UNION ALL SELECT 'telegram_contacts', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM telegram_contacts x
  UNION ALL SELECT 'contact_shares', count(*), md5(coalesce(string_agg(x::text, ',' ORDER BY x::text), '')) FROM contact_shares x
  UNION ALL SELECT 'alembic_version', count(*), max(version_num) FROM alembic_version
) s;

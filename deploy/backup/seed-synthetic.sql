-- Synthetic rows in every table for the restore round trip. Not real people.
INSERT INTO users (id, handle, password_hash, gender, seeking, mode,
                   is_active, consent_version, consent_at, age_confirmed_at)
VALUES
  ('00000000-0000-4000-8000-000000000001', 'restoretest-otter-11', 'x', 'man',
   ARRAY['woman'], 'normal', true, 'test', now(), now()),
  ('00000000-0000-4000-8000-000000000002', 'restoretest-heron-22', 'x', 'woman',
   ARRAY['man', 'other'], 'experimental', true, 'test', now(), now());
INSERT INTO test_scores (user_id, scores) VALUES
  ('00000000-0000-4000-8000-000000000001', '{"dominant": 90, "submissive": 5, "switch": 0}'),
  ('00000000-0000-4000-8000-000000000002', '{"dominant": 5, "submissive": 85, "switch": 40}');
INSERT INTO dislikes (user_id, category_key) VALUES
  ('00000000-0000-4000-8000-000000000001', 'pet'),
  ('00000000-0000-4000-8000-000000000002', 'brat');
INSERT INTO reactions (from_user, to_user, kind) VALUES
  ('00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002', 'like'),
  ('00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000001', 'like');
INSERT INTO matches (id, user_a, user_b) VALUES
  ('00000000-0000-4000-8000-0000000000aa', '00000000-0000-4000-8000-000000000001',
   '00000000-0000-4000-8000-000000000002');
INSERT INTO invites (id, code_hash, expires_at, used_by, used_at) VALUES
  ('00000000-0000-4000-8000-0000000000bb', repeat('a', 64), now() + interval '7 days',
   '00000000-0000-4000-8000-000000000001', now());
INSERT INTO sessions (id, user_id, expires_at) VALUES
  ('00000000-0000-4000-8000-0000000000cc', '00000000-0000-4000-8000-000000000002',
   now() + interval '7 days');
INSERT INTO telegram_contacts (user_id, username_enc) VALUES
  ('00000000-0000-4000-8000-000000000001', 'gAAAAAsynthetic-ciphertext-one'::bytea),
  ('00000000-0000-4000-8000-000000000002', 'gAAAAAsynthetic-ciphertext-two'::bytea);
INSERT INTO contact_shares (match_id, user_id) VALUES
  ('00000000-0000-4000-8000-0000000000aa', '00000000-0000-4000-8000-000000000001');

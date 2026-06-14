-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.issues (
  id text NOT NULL,
  document jsonb NOT NULL,
  embedding jsonb NOT NULL,
  impact_score numeric NOT NULL,
  post_date date NOT NULL,
  traction_date date NOT NULL,
  zone text NOT NULL,
  category text NOT NULL,
  source text NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT issues_pkey PRIMARY KEY (id)
);

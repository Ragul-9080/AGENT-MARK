# Shared library for Agentic Marketing Platform Catalyst functions.
#
# This package contains code common to all functions (config, models, services,
# schemas, integrations). Each function folder (auth/, contacts/, etc.) imports
# from here. When deploying to Catalyst, include this shared/ directory in each
# function's deployment package, or vendor it into each function's requirements.

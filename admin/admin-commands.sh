#!/usr/bin/env bash
#/ admin-commands.sh - v0.1.0
#/
#/ Commands
#/ -----------------
#/ bump {major,minor,patch}
#/ version
#/
#/
#/
#/
#/
#/ -------------------------------------

# VARIABLES
# --------------------------------------
ADMIN_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
FUNCTIONS_SH_PATH="${ADMIN_DIR}/admin-functions.sh"
ADMIN_CONFIG_YAML="${ADMIN_DIR}/.admin-config.yaml"
# --------------------------------------

if [[ -f "${FUNCTIONS_SH_PATH}" ]]
then
    echo "Found functions at ${FUNCTIONS_SH_PATH}"
else
    echo "Failed to admin-functions.sh file. (Looked at ${FUNCTIONS_SH_PATH}) Aborting..."
    exit 1
fi

# Source functions
source ${FUNCTIONS_SH_PATH}
# Read in the yaml file, create variables for the items therein
create_variables ${ADMIN_CONFIG_YAML} ""

announce_section "Scanning for needed files..."
if [[ ! -d ${PROJECT_DIR} ]]
then
    make_log "error The project directory at path '${PROJECT_DIR}' was not found."
    exit 1
fi

PYPROJECT_TOML_FPATH="${PROJECT_DIR}/pyproject.toml"
PY_INIT_FPATH="${PROJECT_DIR}/${PY_LIB_NAME}/__init__.py"
CHANGELOG_PATH="${PROJECT_DIR}/CHANGELOG.md"

do_bump () {
  # Get current version and calculate the new version based on level input
  make_log "debug Determining version bump..."
  bump_version ${PYPROJECT_TOML_FPATH} ${LEVEL}

  # Build changelog string
  CHGLOG_STR="\ \n### [${NEW_VERSION}] - $(date +"%Y-%m-%d")\n#### Added\n#### Changed\n#### Deprecated\n#### Removed\n#### Fixed\n#### Security"

  CONFIRM_TXT=$(echo -e "Creating a ${GRN}RELEASE${RST}. Updating version '${BLU}${CUR_VERSION}${RST}' to '${RED}${NEW_VERSION}${RST}' in:\n\t - ${PYPROJECT_TOML_FPATH} \n\t - ${PY_INIT_FPATH} \n\t - ${CHANGELOG_PATH}\n ")

  # Confirm
  read -p $"Confirm (y/n): ${CONFIRM_TXT}" -n 1 -r
  echo # (optional) move to a new line

  if [[ ${REPLY} =~ ^[Yy]$ ]]
  then
      # 1. Apply new version & update date to file
      make_log "debug Applying new version to files..."
      # Logic: "Find line beginning with __version__, replace with such at file
      if [[ -f "${PY_INIT_FPATH}" ]]
      then
        make_log "debug Applying to ${PY_INIT_FPATH} ..."
        sed -i "s/^__version__.*/__version__ = '${NEW_VERSION}'/" ${PY_INIT_FPATH}
        sed -i "s/^__update_date__.*/__update_date__ = '$(date +"%Y-%m-%d_%H:%M:%S")'/" ${PY_INIT_FPATH}
      else
        make_log "warn Skipping ${PY_INIT_FPATH} - No file found."
      fi
      # 1.1. Add version to pyproject.toml
      sed -i "s/^version =.*/version = '${NEW_VERSION}'/" ${PYPROJECT_TOML_FPATH}
      # 2. Insert new section and link in CHANGELOG.md
      if [[ -f "${CHANGELOG_PATH}" ]]
      then
        make_log "debug Inserting new area in CHANGELOG for version..."
        sed -i.bak "/__BEGIN-CHANGELOG__/a ${CHGLOG_STR}" ${CHANGELOG_PATH}
      else
        make_log "warn Skipping ${CHANGELOG_PATH} - No file found."
      fi
      make_log "info New version is ${RED}${NEW_VERSION}${RESET}"
      make_log "info To finish, fill in CHANGELOG details and then ${RED}make push${RESET}"
  else
      make_log "info Cancelled procedure"
  fi

}

do_pull () {
  make_log "debug Confirming branch..."
  confirm_branch ${MAIN_BRANCH}
  # Update procedure
  make_log "debug Pulling updates from remote ${RED}${MAIN_BRANCH}${RESET}..."
  (git -C $PROJECT_DIR pull origin ${MAIN_BRANCH})
}

do_tag_and_push () {
  make_log "debug Confirming branch..."
  confirm_branch ${MAIN_BRANCH}
  # Push to remote, tag
  make_log "debug Getting version..."
  get_version ${PYPROJECT_TOML_FPATH}
  CUR_VERSION="v${CUR_VERSION}"
  # First get the staged changes
  STAGED_ITEMS_TXT="$(git -C ${PROJECT_DIR} diff --shortstat)"
  CONFIRM_TXT=$(echo -e "Tagging the following changes with version ${RED}${CUR_VERSION}${RST} to ${RED}${MAIN_BRANCH}${RST}: \n\t${PRP}${STAGED_ITEMS_TXT}${RST} \n ")
  # Confirm
  read -p $"Confirm (y/n): ${CONFIRM_TXT}" -n 1 -r
  if [[ ${REPLY} =~ ^[Yy]$ ]]
  then
      # Get current hash and see if it already has a tag
      make_log "debug Grabbing commit"
      GIT_COMMIT=$(git -C ${REPO_DIR} rev-parse HEAD)
      make_log "debug Determining if needs tag"
      NEEDS_TAG=$(git -C ${REPO_DIR} describe --contains ${GIT_COMMIT})
      # Only tag if no tag already (would be better if the git describe command above could have a silent option)
      if [[ -z "$NEEDS_TAG" ]]; then
          make_log "debug Tagged with ${CUR_VERSION} (Ignoring fatal:cannot describe - this means commit is untagged) "
          git -C ${PROJECT_DIR} tag ${CUR_VERSION}
          make_log "debug Pushing tag to ${MAIN_BRANCH}"
          git -C ${PROJECT_DIR} push --tags origin ${MAIN_BRANCH}
      else
          make_log "debug Already a tag on this commit"
      fi
  else
      make_log "info Aborted tag."
  fi
}

announce_section "Handling command '${CMD}'..."
if [[ ${CMD} == 'bump' ]]
then
    do_bump
elif [[ ${CMD} == 'pull' ]]
then
    do_pull
elif [[ ${CMD} == 'push' ]]
then
    do_tag_and_push
else
    make_log "info No command matched (push|pull|bump)"
fi
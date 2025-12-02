# Resume Templates

This directory contains template resumes for getting started with Henry the Hire Tracker.

## How to Use These Templates

1. **Copy the template(s) you want** to the parent `resumes/` directory
2. **Remove `_template` from the filename**
   - Example: `backend_developer_resume_template.txt` → `backend_developer_resume.txt`
3. **Replace all placeholders** with your actual information:
   - `[YOUR_NAME]` → Your full name
   - `[YOUR_EMAIL]` → Your email address
   - `[YOUR_PHONE]` → Your phone number
   - `[YOUR_LOCATION]` → Your city, state
   - `[YOUR_WEBSITE]` → Your personal website
   - `[YOUR_LINKEDIN]` → Your LinkedIn profile URL
   - `[YOUR_GITHUB]` → Your GitHub profile URL
   - `[PROJECT_NAME_#]` → Names of your projects
   - `[JOB_TITLE]` → Your job titles
   - `[COMPANY_NAME]` → Company names
   - And so on...

4. **Update your `config.yaml`** to point to your resume files:
   ```yaml
   resumes:
     files:
       - "resumes/backend_developer_resume.txt"
       - "resumes/cloud_engineer_resume.txt"
       - "resumes/fullstack_developer_resume.txt"
   ```

## Template Types

### `backend_developer_resume_template.txt`
Use this template if you focus on:
- Backend development
- API design
- Distributed systems
- Database architecture
- Server-side technologies

### `cloud_engineer_resume_template.txt`
Use this template if you focus on:
- Cloud infrastructure (AWS, Azure, GCP)
- Infrastructure as Code (Terraform, CloudFormation, etc.)
- DevOps and CI/CD
- Cost optimization
- High-availability systems

### `fullstack_developer_resume_template.txt`
Use this template if you focus on:
- Full-stack development
- Frontend frameworks (React, Vue, Angular, etc.)
- Backend services
- Database integration
- End-to-end application development

## Tips for Multiple Resume Variants

You don't need all three resumes! Create only what makes sense for your background:

- **One resume**: If you have a clear specialty, use one targeted resume
- **Two resumes**: If you apply to both backend and full-stack roles, create both
- **Three resumes**: If you want to target backend, cloud, and full-stack positions separately

The AI will automatically recommend which resume to use for each job based on the job description and your configured resume variants in `config.yaml`.

## Privacy Note

Your actual resume files (without `_template` in the name) are automatically ignored by git (see `.gitignore`), so your personal information stays private when you push to a public repository.

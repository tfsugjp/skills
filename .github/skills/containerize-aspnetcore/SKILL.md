---
name: containerize-aspnetcore
description: 'Containerize an ASP.NET Core project by creating Dockerfile and .dockerfile files customized for the project.'
---

# ASP.NET Core Docker Containerization Prompt

## Containerization Request

Containerize the ASP.NET Core (.NET) project specified in the settings below, focusing **exclusively** on changes required for the application to run in a Linux Docker container. Follow best practices for containerizing .NET Core applications, ensuring that the container is optimized for performance, security, and maintainability.

## Containerization Settings

### Basic Project Information
1. Project to containerize: `[ProjectName (provide path to .csproj file)]`
2. .NET version to use: `[8.0 or 9.0 (Default 8.0)]`
3. Linux distribution: `[debian, alpine, ubuntu, chiseled, or Azure Linux (mariner) (Default debian)]`

### Container Configuration
1. Ports to expose: Primary HTTP port `[e.g., 8080]`
2. User account: `[User account, or default to "$APP_UID"]`
3. Application URL: `[ASPNETCORE_URLS, or default to "http://+:8080"]`

### Dependencies
1. System packages: `[Package names, or "None"]`
2. Native libraries: `[Library names and paths, or "None"]`
3. Additional .NET tools: `[Tool names and versions, or "None"]`

## Execution Process

1. Determine the .NET version from the project's .csproj `TargetFramework` element
2. Select appropriate Linux container image based on .NET version and Linux distribution
3. Create a multi-stage Dockerfile:
   - **Build stage**: Use .NET SDK image to build and publish the application
   - **Final stage**: Use .NET runtime image to run the application
4. Create a `.dockerignore` file excluding unnecessary files
5. Configure health checks if a health endpoint is provided
6. Run `docker build -t aspnetcore-app:latest .` to verify

## Example Dockerfile

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0-bookworm-slim AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
COPY ["YourProject/YourProject.csproj", "YourProject/"]
RUN dotnet restore "YourProject/YourProject.csproj"
COPY . .
WORKDIR "/src/YourProject"
RUN dotnet publish "YourProject.csproj" -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:8.0-bookworm-slim AS final
WORKDIR /app
ENV ASPNETCORE_ENVIRONMENT=Production
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
COPY --from=build /app/publish .
USER $APP_UID
ENTRYPOINT ["dotnet", "YourProject.dll"]
```

## Linux Distribution Variations

### Alpine Linux
```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:8.0-alpine AS build
FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS final
RUN apk update && apk add --no-cache curl ca-certificates
```

### Ubuntu Chiseled (minimal attack surface)
```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0-jammy-chiseled AS final
```

### Azure Linux (Mariner)
```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:8.0-azurelinux3.0 AS final
RUN tdnf update -y && tdnf install -y curl ca-certificates && tdnf clean all
```

## Security Best Practices

- Always run as a non-root user in production (`USER $APP_UID`)
- Use specific image tags instead of `latest`
- Minimize the number of installed packages
- Use multi-stage builds to exclude build dependencies
- Keep base images updated

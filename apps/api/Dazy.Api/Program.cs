using Dazy.Api;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy
            .WithOrigins("http://localhost:5173", "http://localhost:5174")
            .AllowAnyHeader()
            .AllowAnyMethod();
    });
});

var app = builder.Build();

app.UseCors();

var group = app.MapGroup("/api/v1");

group.MapGet("/health", () => Results.Ok(new { status = "ok", app = "Dazy.club API" }));
group.MapGet("/sports", () => Results.Ok(SeedData.Sports));
group.MapGet("/gallery", () => Results.Ok(SeedData.GalleryItems));
group.MapGet("/testimonials", () => Results.Ok(SeedData.Testimonials));
group.MapGet("/notifications", () => Results.Ok(SeedData.Notifications));

group.MapPost("/contact-enquiries", (ContactEnquiryRequest request) =>
{
    var errors = request.Validate();
    return errors.Count > 0
        ? Results.ValidationProblem(errors)
        : Results.Created($"/api/v1/contact-enquiries/{Guid.NewGuid()}", new { status = "received", request.Name });
});

group.MapPost("/corporate-enquiries", (CorporateEnquiryRequest request) =>
{
    var errors = request.Validate();
    return errors.Count > 0
        ? Results.ValidationProblem(errors)
        : Results.Created($"/api/v1/corporate-enquiries/{Guid.NewGuid()}", new { status = "received", request.Company });
});

app.MapGet("/", () => Results.Ok(new { app = "Dazy.club API", docs = "/api/v1/health" }));

app.Run();

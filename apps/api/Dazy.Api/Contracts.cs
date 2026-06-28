namespace Dazy.Api;

public sealed record SportDto(
    string Id,
    string Slug,
    string Name,
    string Tagline,
    string Description,
    string[] Highlights);

public sealed record GalleryItemDto(string Id, string Title, string SportSlug, string Tone);

public sealed record TestimonialDto(string Id, string Name, string Context, string Quote);

public sealed record NotificationDto(string Id, string Title, string Body, string Surface);

public sealed record ContactEnquiryRequest(
    string? Name,
    string? Contact,
    string? InterestedSport,
    string? Message)
{
    public Dictionary<string, string[]> Validate()
    {
        var errors = new Dictionary<string, string[]>();
        if (string.IsNullOrWhiteSpace(Name)) errors["name"] = ["Name is required."];
        if (string.IsNullOrWhiteSpace(Contact)) errors["contact"] = ["Phone or email is required."];
        return errors;
    }
}

public sealed record CorporateEnquiryRequest(
    string? ContactName,
    string? Company,
    string? Contact,
    string? EventType,
    int? EstimatedGroupSize,
    string? PreferredDate,
    string? PreferredSport,
    string? Message)
{
    public Dictionary<string, string[]> Validate()
    {
        var errors = new Dictionary<string, string[]>();
        if (string.IsNullOrWhiteSpace(ContactName)) errors["contactName"] = ["Contact name is required."];
        if (string.IsNullOrWhiteSpace(Company)) errors["company"] = ["Company is required."];
        if (string.IsNullOrWhiteSpace(Contact)) errors["contact"] = ["Phone or email is required."];
        if (EstimatedGroupSize is < 1) errors["estimatedGroupSize"] = ["Group size must be positive."];
        return errors;
    }
}

#pragma once
// Small, dependency-free UTF-8 JSON value for the local desktop protocol.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
#include <type_traits>

namespace pf {
template<class A,class B> constexpr std::common_type_t<A,B> min(A a,B b){using T=std::common_type_t<A,B>;return T(a)<T(b)?T(a):T(b);}
template<class A,class B> constexpr std::common_type_t<A,B> max(A a,B b){using T=std::common_type_t<A,B>;return T(a)>T(b)?T(a):T(b);}
template<class T> T min(std::initializer_list<T> a){return *std::min_element(a.begin(),a.end());}
template<class T> T max(std::initializer_list<T> a){return *std::max_element(a.begin(),a.end());}
template<class A,class B,class C> constexpr std::common_type_t<A,B,C> clamp(A a,B lo,C hi){using T=std::common_type_t<A,B,C>;return max(T(lo),min(T(a),T(hi)));}
struct Json {
    using Array = std::vector<Json>;
    using Object = std::map<std::string, Json>;
    std::variant<std::nullptr_t, bool, double, std::string, Array, Object> v;
    Json() : v(nullptr) {}
    Json(std::nullptr_t) : v(nullptr) {}
    Json(bool x) : v(x) {}
    Json(int x) : v(double(x)) {}
    Json(long x) : v(double(x)) {}
    Json(unsigned int x) : v(double(x)) {}
    Json(unsigned long x) : v(double(x)) {}
    Json(long long x) : v(double(x)) {}
    Json(size_t x) : v(double(x)) {}
    Json(double x) : v(x) { if (!std::isfinite(x)) throw std::runtime_error("Non-finite JSON number"); }
    Json(const char* x) : v(std::string(x)) {}
    Json(std::string x) : v(std::move(x)) {}
    Json(Array x) : v(std::move(x)) {}
    Json(Object x) : v(std::move(x)) {}
    static Json object(std::initializer_list<Object::value_type> x = {}) { return Object(x); }
    static Json array(std::initializer_list<Json> x = {}) { return Array(x); }
    bool null() const { return std::holds_alternative<std::nullptr_t>(v); }
    bool isObject() const { return std::holds_alternative<Object>(v); }
    bool isArray() const { return std::holds_alternative<Array>(v); }
    bool isString() const { return std::holds_alternative<std::string>(v); }
    bool isNumber() const { return std::holds_alternative<double>(v); }
    bool isBool() const { return std::holds_alternative<bool>(v); }
    const Object& obj() const { return std::get<Object>(v); }
    Object& obj() { return std::get<Object>(v); }
    const Array& arr() const { return std::get<Array>(v); }
    Array& arr() { return std::get<Array>(v); }
    std::string str(std::string fallback = "") const { return isString() ? std::get<std::string>(v) : fallback; }
    double number(double fallback = 0) const { return isNumber() ? std::get<double>(v) : fallback; }
    int integer(int fallback = 0) const { auto n = number(fallback); if (n < -2147483648. || n > 2147483647. || n != std::floor(n)) throw std::runtime_error("Expected bounded integer"); return int(n); }
    bool boolean(bool fallback = false) const { return isBool() ? std::get<bool>(v) : fallback; }
    size_t size() const { return isArray() ? arr().size() : isObject() ? obj().size() : 0; }
    bool empty() const { return size()==0; }
    bool contains(const std::string& k) const { return isObject() && obj().count(k); }
    const Json& operator[](const std::string& k) const { static const Json empty; if (!isObject()) return empty; auto i=obj().find(k); return i==obj().end()?empty:i->second; }
    Json& operator[](const std::string& k) { if (null()) v=Object(); return obj()[k]; }
    const Json& operator[](size_t i) const { return arr().at(i); }
    Json& operator[](size_t i) { return arr().at(i); }
    bool operator==(const Json& other) const { return v == other.v; }
    bool operator!=(const Json& other) const { return !(*this==other); }
    static void utf8(std::string& s, unsigned c) {
        if(c<0x80) s+=char(c);
        else if(c<0x800) {s+=char(0xc0|(c>>6));s+=char(0x80|(c&63));}
        else if(c<0x10000) {s+=char(0xe0|(c>>12));s+=char(0x80|((c>>6)&63));s+=char(0x80|(c&63));}
        else {s+=char(0xf0|(c>>18));s+=char(0x80|((c>>12)&63));s+=char(0x80|((c>>6)&63));s+=char(0x80|(c&63));}
    }
    static std::string quote(const std::string& s) {
        std::string out="\"";
        for(unsigned char c:s) {switch(c) {case '"':out+="\\\"";break;case '\\':out+="\\\\";break;case '\b':out+="\\b";break;case '\f':out+="\\f";break;case '\n':out+="\\n";break;case '\r':out+="\\r";break;case '\t':out+="\\t";break;default:if(c<32){char b[8];std::snprintf(b,sizeof b,"\\u%04x",c);out+=b;}else out+=char(c);}}
        return out+'"';
    }
    std::string dump() const {
        if(null())return "null"; if(isBool())return boolean()?"true":"false";
        if(isNumber()){char b[64];std::snprintf(b,sizeof b,"%.17g",number());return b;}
        if(isString())return quote(str());
        std::string s=isArray()?"[":"{";bool first=true;
        if(isArray())for(auto& x:arr()){if(!first)s+=',';first=false;s+=x.dump();}
        else for(auto& [k,x]:obj()){if(!first)s+=',';first=false;s+=quote(k)+':'+x.dump();}
        return s+(isArray()?"]":"}");
    }
    struct Parser;
    static Json parse(const std::string& s);
};
struct Json::Parser {
    const std::string& s; size_t p=0;
    [[noreturn]] void fail() const { throw std::runtime_error("Invalid JSON at byte "+std::to_string(p)); }
    void ws(){while(p<s.size()&&(s[p]==' '||s[p]=='\n'||s[p]=='\r'||s[p]=='\t'))++p;}
    bool eat(char c){ws();if(p<s.size()&&s[p]==c){++p;return true;}return false;}
    unsigned hex(){if(p+4>s.size())fail();unsigned x=0;for(int n=0;n<4;++n){char c=s[p++];x<<=4;if(c>='0'&&c<='9')x+=c-'0';else if(c>='a'&&c<='f')x+=10+c-'a';else if(c>='A'&&c<='F')x+=10+c-'A';else fail();}return x;}
    std::string string(){if(!eat('"'))fail();std::string out;while(p<s.size()){unsigned char c=s[p++];if(c=='"')return out;if(c<32)fail();if(c!='\\'){out+=char(c);continue;}if(p==s.size())fail();switch(s[p++]){case '"':out+='"';break;case '\\':out+='\\';break;case '/':out+='/';break;case 'b':out+='\b';break;case 'f':out+='\f';break;case 'n':out+='\n';break;case 'r':out+='\r';break;case 't':out+='\t';break;case 'u':{unsigned x=hex();if(x>=0xd800&&x<=0xdbff){if(p+2>s.size()||s[p++]!='\\'||s[p++]!='u')fail();auto low=hex();if(low<0xdc00||low>0xdfff)fail();x=0x10000+((x-0xd800)<<10)+(low-0xdc00);}else if(x>=0xdc00&&x<=0xdfff)fail();utf8(out,x);break;}default:fail();}}fail();}
    Json value(int depth=0){if(depth>80)fail();ws();if(p==s.size())fail();char c=s[p];
        if(c=='"')return string();
        if(eat('{')){Object obj;if(eat('}'))return obj;do{auto k=string();if(!eat(':')||obj.count(k))fail();obj[k]=value(depth+1);}while(eat(','));if(!eat('}'))fail();return obj;}
        if(eat('[')){Array a;if(eat(']'))return a;do{a.push_back(value(depth+1));}while(eat(','));if(!eat(']'))fail();return a;}
        for(auto [word,literal]:{std::pair<const char*,Json>{"true",true},{"false",false},{"null",nullptr}}){size_t n=std::char_traits<char>::length(word);if(s.compare(p,n,word)==0){p+=n;return literal;}}
        size_t start=p;if(s[p]=='-')++p;if(p==s.size())fail();if(s[p]=='0')++p;else{if(s[p]<'1'||s[p]>'9')fail();while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;}
        if(p<s.size()&&s[p]=='.'){++p;auto q=p;while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;if(p==q)fail();}
        if(p<s.size()&&(s[p]=='e'||s[p]=='E')){++p;if(p<s.size()&&(s[p]=='+'||s[p]=='-'))++p;auto q=p;while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;if(p==q)fail();}
        char* end=nullptr;auto token=s.substr(start,p-start);double n=std::strtod(token.c_str(),&end);if(!std::isfinite(n)||*end)fail();return n;
    }
};
inline Json Json::parse(const std::string& s){if(s.size()>128*1024*1024)throw std::runtime_error("JSON too large");Parser p{s};auto result=p.value();p.ws();if(p.p!=s.size())p.fail();return result;}
using J=Json;
}
